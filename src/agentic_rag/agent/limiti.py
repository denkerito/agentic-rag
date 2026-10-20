"""Limitatore di richieste (opzionale) per qualsiasi modello Pydantic AI, e misura delle attese.

Senza limiti configurati il modello non viene avvolto. Con limiti, prima di ogni richiesta si attende
finché nell'ultimo minuto restano richieste (RPM) e token (TPM) disponibili. Il tempo atteso si somma
nella `MisuraAttese` attiva, così l'eval può tenerlo fuori dalla latenza e dal timeout.
"""

import asyncio
import time
from collections import deque
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from pydantic_ai.messages import ModelMessage, ModelResponse
from pydantic_ai.models import KnownModelName, Model, ModelRequestParameters, StreamedResponse
from pydantic_ai.models.wrapper import WrapperModel
from pydantic_ai.settings import ModelSettings

FINESTRA_S = 60.0
PASSO_ATTESA_S = 1.0  # l'attesa si accumula a passi: il watchdog del timeout la vede crescere


@dataclass
class MisuraAttese:
    secondi: float = 0.0
    tentativi_falliti: int = 0  # richieste al provider fallite e ritentate (429, 5xx, rete)


_misura: ContextVar[MisuraAttese | None] = ContextVar("misura_attese", default=None)


@contextmanager
def misura_attese() -> Iterator[MisuraAttese]:
    """Raccoglie i secondi attesi dai limitatori nel contesto corrente (e nei task che crea)."""
    misura = MisuraAttese()
    token = _misura.set(misura)
    try:
        yield misura
    finally:
        _misura.reset(token)


def aggiungi_attesa(secondi: float) -> None:
    """Somma secondi alla misura attiva, se c'è (nell'API non ce n'è: non fa nulla)."""
    misura = _misura.get()
    if misura is not None:
        misura.secondi += secondi


def conta_tentativo_fallito() -> None:
    misura = _misura.get()
    if misura is not None:
        misura.tentativi_falliti += 1


async def dormi_misurato(
    secondi: float, dormi: Callable[[float], Awaitable[None]] = asyncio.sleep
) -> None:
    """Dorme a passi di PASSO_ATTESA_S sommandoli alla misura: il watchdog la vede crescere."""
    resto = secondi
    while resto > 0:
        passo = min(resto, PASSO_ATTESA_S)
        await dormi(passo)
        aggiungi_attesa(passo)
        resto -= passo


class Limitatore:
    """Finestra scorrevole di 60 s su richieste e token. Un'istanza per modello, nel processo."""

    def __init__(
        self,
        rpm: int | None,
        tpm: int | None,
        orologio: Callable[[], float] = time.monotonic,
        dormi: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.rpm = rpm
        self.tpm = tpm
        self._orologio = orologio
        self._dormi = dormi
        self._richieste: deque[float] = deque()
        self._token: deque[tuple[float, int]] = deque()

    def _pulisci(self, adesso: float) -> None:
        while self._richieste and adesso - self._richieste[0] >= FINESTRA_S:
            self._richieste.popleft()
        while self._token and adesso - self._token[0][0] >= FINESTRA_S:
            self._token.popleft()

    def _attesa_necessaria(self, adesso: float) -> float:
        attesa = 0.0
        if self.rpm and len(self._richieste) >= self.rpm:
            attesa = max(attesa, self._richieste[0] + FINESTRA_S - adesso)
        if self.tpm and sum(n for _, n in self._token) >= self.tpm:
            attesa = max(attesa, self._token[0][0] + FINESTRA_S - adesso)
        return attesa

    async def attendi(self) -> float:
        """Attende uno slot libero e registra la richiesta. Restituisce i secondi attesi."""
        totale = 0.0
        while True:
            adesso = self._orologio()
            self._pulisci(adesso)
            attesa = self._attesa_necessaria(adesso)
            if attesa <= 0:
                self._richieste.append(adesso)
                return totale
            passo = min(attesa, PASSO_ATTESA_S)
            await self._dormi(passo)
            totale += passo
            aggiungi_attesa(passo)

    def registra_token(self, n: int) -> None:
        if n > 0:
            self._token.append((self._orologio(), n))


class ModelloLimitato(WrapperModel):
    def __init__(self, wrapped: Model | KnownModelName, limitatore: Limitatore) -> None:
        super().__init__(wrapped)
        self.limitatore = limitatore

    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        await self.limitatore.attendi()
        risposta = await super().request(messages, model_settings, model_request_parameters)
        self.limitatore.registra_token(risposta.usage.input_tokens + risposta.usage.output_tokens)
        return risposta

    @asynccontextmanager
    async def request_stream(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
        run_context: Any = None,
    ) -> AsyncIterator[StreamedResponse]:
        await self.limitatore.attendi()
        async with super().request_stream(
            messages, model_settings, model_request_parameters, run_context
        ) as stream:
            yield stream
        u = stream.usage()
        self.limitatore.registra_token(u.input_tokens + u.output_tokens)


_limitatori: dict[tuple[str, str], Limitatore] = {}


def limitatore_per(ruolo: str, nome: str, rpm: int | None, tpm: int | None) -> Limitatore | None:
    """Limitatore condiviso per (ruolo, modello): la finestra sopravvive tra una domanda e l'altra."""
    if not rpm and not tpm:
        return None
    chiave = (ruolo, nome)
    if chiave not in _limitatori:
        _limitatori[chiave] = Limitatore(rpm, tpm)
    return _limitatori[chiave]
