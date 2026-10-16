import httpx
import pytest
from pydantic_ai.exceptions import ModelAPIError, ModelHTTPError, UsageLimitExceeded

from agentic_rag.eval.runner import errore_di_infrastruttura


@pytest.mark.parametrize(
    "errore",
    [
        httpx.ReadError("connessione chiusa"),
        httpx.ConnectTimeout("timeout"),
        TimeoutError(),
        ConnectionResetError(),
        ModelHTTPError(429, "google:m"),
        ModelHTTPError(503, "google:m"),
        ModelAPIError("google:m", "rete"),
    ],
)
def test_errori_di_rete_e_provider_si_rieseguono(errore) -> None:
    assert errore_di_infrastruttura(errore)


@pytest.mark.parametrize(
    "errore",
    [UsageLimitExceeded("limite"), ModelHTTPError(400, "google:m"), RuntimeError("boom")],
)
def test_errori_dell_agente_o_della_richiesta_non_si_rieseguono(errore) -> None:
    assert not errore_di_infrastruttura(errore)
