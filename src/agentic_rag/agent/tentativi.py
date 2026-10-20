"""Tentativi su errori temporanei del provider (429, 5xx, rete), fatti dal wrapper e non dal client.

Le pause e la durata dei tentativi falliti si sommano nella `MisuraAttese` attiva: l'eval le tiene
fuori dal tempo di lavoro, così un provider instabile non diventa un fallimento dell'agente.
"""

import random
from collections.abc import Callable
from dataclasses import dataclass

import httpx
from google.genai import errors as genai_errors
from pydantic_ai.exceptions import ModelHTTPError

# Stessi codici ritentati prima dal client Gemini (RETRY_429).
CODICI_TEMPORANEI: tuple[int, ...] = (429, 500, 502, 503, 504)


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
    return isinstance(e, (httpx.TimeoutException, httpx.ConnectError, TimeoutError))
