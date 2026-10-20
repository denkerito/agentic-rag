"""Tentativi su errori temporanei del provider (429, 5xx, rete), fatti dal wrapper e non dal client.

Le pause e la durata dei tentativi falliti si sommano nella `MisuraAttese` attiva: l'eval le tiene
fuori dal tempo di lavoro, così un provider instabile non diventa un fallimento dell'agente.
"""

import asyncio
import random
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from typing import Any

import httpx
from google.genai import errors as genai_errors
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import ModelMessage, ModelResponse
from pydantic_ai.models import KnownModelName, Model, ModelRequestParameters, StreamedResponse
from pydantic_ai.models.wrapper import WrapperModel
from pydantic_ai.settings import ModelSettings

from agentic_rag.agent.limiti import (
    Limitatore,
    aggiungi_attesa,
    conta_tentativo_fallito,
    dormi_misurato,
)

# Stessi codici ritentati prima dal client Gemini (RETRY_429).
CODICI_TEMPORANEI: tuple[int, ...] = (429, 500, 502, 503, 504)
# Errori di rete: anche le disconnessioni a metà risposta (ReadError, RemoteProtocolError), che
# google-genai lascia passare come errori httpx. L'eval usa la stessa definizione.
ERRORI_RETE: tuple[type[BaseException], ...] = (httpx.TransportError, ConnectionError, TimeoutError)


@dataclass(frozen=True)
class PoliticaTentativi:
    tentativi: int = 5  # compreso il primo
    attesa_iniziale_s: float = 10.0  # pause 10, 20, 40, 60 s come la vecchia cadenza
    attesa_max_s: float = 60.0
    jitter_s: float = 1.0
    # oltre questo un tentativo si considera bloccato e si ritenta (il timeout HTTP è 600 s)
    timeout_tentativo_s: float | None = 120.0


POLITICA = PoliticaTentativi()


def pausa(
    politica: PoliticaTentativi, n: int, casuale: Callable[[], float] = random.random
) -> float:
    """Pausa dopo l'n-esimo tentativo fallito (n da 1)."""
    base = min(politica.attesa_iniziale_s * 2 ** (n - 1), politica.attesa_max_s)
    return base + politica.jitter_s * casuale()


def da_ritentare(e: BaseException) -> bool:
    """Errori temporanei del provider o della rete. CancelledError e gli errori dell'agente no."""
    if isinstance(e, ModelHTTPError):
        return e.status_code in CODICI_TEMPORANEI
    if isinstance(e, genai_errors.APIError):
        return e.code in CODICI_TEMPORANEI
    return isinstance(e, ERRORI_RETE)


class ModelloGestito(WrapperModel):
    """Limitatore RPM/TPM opzionale e tentativi su errori temporanei, attorno a qualsiasi modello.

    Ogni tentativo passa dal limitatore. Durata dei tentativi falliti e pause finiscono nella
    `MisuraAttese` attiva. Nello streaming si ritenta solo l'apertura: dopo il primo evento no.
    """

    def __init__(
        self,
        wrapped: Model | KnownModelName,
        limitatore: Limitatore | None,
        politica: PoliticaTentativi = POLITICA,
        orologio: Callable[[], float] = time.monotonic,
        dormi: Callable[[float], Awaitable[None]] = asyncio.sleep,
        casuale: Callable[[], float] = random.random,
    ) -> None:
        super().__init__(wrapped)
        self.limitatore = limitatore
        self.politica = politica
        self._orologio = orologio
        self._dormi = dormi
        self._casuale = casuale

    async def _con_tentativi[T](self, tentativo: Callable[[], Awaitable[T]]) -> T:
        n = 1
        while True:
            if self.limitatore:
                await self.limitatore.attendi()
            inizio = self._orologio()
            try:
                return await asyncio.wait_for(tentativo(), self.politica.timeout_tentativo_s)
            except Exception as e:
                if not da_ritentare(e):
                    raise
                aggiungi_attesa(self._orologio() - inizio)
                conta_tentativo_fallito()
                if n >= self.politica.tentativi:
                    raise
                await dormi_misurato(pausa(self.politica, n, self._casuale), self._dormi)
                n += 1

    def _registra_token(self, input_tokens: int, output_tokens: int) -> None:
        if self.limitatore:
            self.limitatore.registra_token(input_tokens + output_tokens)

    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        risposta = await self._con_tentativi(
            lambda: self.wrapped.request(messages, model_settings, model_request_parameters)
        )
        self._registra_token(risposta.usage.input_tokens, risposta.usage.output_tokens)
        return risposta

    @asynccontextmanager
    async def request_stream(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
        run_context: Any = None,
    ) -> AsyncIterator[StreamedResponse]:
        async with AsyncExitStack() as stack:
            stream = await self._con_tentativi(
                lambda: stack.enter_async_context(
                    self.wrapped.request_stream(
                        messages, model_settings, model_request_parameters, run_context
                    )
                )
            )
            yield stream
        u = stream.usage
        self._registra_token(u.input_tokens, u.output_tokens)
