import asyncio

import httpx
from google.genai import errors as genai_errors
from pydantic_ai.exceptions import ModelHTTPError, UnexpectedModelBehavior, UsageLimitExceeded

from agentic_rag.agent.tentativi import POLITICA, da_ritentare, pausa


def test_pausa_segue_la_cadenza_di_prima() -> None:
    assert [pausa(POLITICA, n, casuale=lambda: 0.0) for n in range(1, 6)] == [10, 20, 40, 60, 60]
    assert pausa(POLITICA, 1, casuale=lambda: 1.0) == 11


def test_da_ritentare() -> None:
    for codice in (429, 500, 502, 503, 504):
        assert da_ritentare(ModelHTTPError(status_code=codice, model_name="m"))
    assert da_ritentare(genai_errors.APIError(503, {}))
    assert da_ritentare(httpx.ConnectError("giù"))
    assert da_ritentare(httpx.ReadTimeout("lento"))
    assert da_ritentare(TimeoutError())  # timeout del singolo tentativo
    assert not da_ritentare(ModelHTTPError(status_code=400, model_name="m"))
    assert not da_ritentare(ModelHTTPError(status_code=404, model_name="m"))
    assert not da_ritentare(genai_errors.APIError(400, {}))
    assert not da_ritentare(UsageLimitExceeded("limite"))
    assert not da_ritentare(UnexpectedModelBehavior("output non valido"))
    assert not da_ritentare(asyncio.CancelledError())
