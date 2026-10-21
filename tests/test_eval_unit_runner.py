import asyncio

import httpx
import psycopg
import pytest
from pydantic_ai.exceptions import ModelAPIError, ModelHTTPError, UsageLimitExceeded
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    TextPart,
)
from pydantic_ai.models import ModelRequestParameters
from pydantic_ai.models.function import AgentInfo, FunctionModel

from agentic_rag.agent.agent import RIFIUTO_CAUSA_NON_LETTA
from agentic_rag.agent.limiti import misura_attese
from agentic_rag.agent.tentativi import ModelloGestito, PoliticaTentativi
from agentic_rag.eval.runner import (
    costo_risposte,
    entro_il_tempo,
    errore_di_infrastruttura,
    errore_fatale,
    rifiuti_del_validatore,
)


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
        psycopg.OperationalError("server closed the connection"),  # DB giù durante la run
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


def test_il_nome_dell_errore_include_il_codice_http() -> None:
    from agentic_rag.eval.runner import nome_errore

    assert nome_errore(ModelHTTPError(503, "google:m")) == "ModelHTTPError 503"
    assert nome_errore(TimeoutError()) == "TimeoutError"


def test_tentativi_del_provider_non_consumano_il_tempo_di_lavoro() -> None:
    # tentativo fallito da 3 s + pausa da 2 s = 5 s persi per il provider, timeout di lavoro 4 s:
    # prima della modifica (attese nel client, non misurate) scattava TempoScaduto
    t = [0.0]
    chiamate = 0

    def provider(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        nonlocal chiamate
        chiamate += 1
        if chiamate == 1:
            t[0] += 3
            raise ModelHTTPError(status_code=503, model_name="f")
        return ModelResponse(parts=[TextPart("ok")])

    async def dormi_lento(s: float) -> None:
        t[0] += s
        await asyncio.sleep(0.3)  # tempo reale: il watchdog (ogni 0,2 s) controlla durante la pausa

    modello = ModelloGestito(
        FunctionModel(provider),
        None,
        PoliticaTentativi(attesa_iniziale_s=2.0, jitter_s=0.0),
        orologio=lambda: t[0],
        dormi=dormi_lento,
    )
    richiesta = modello.request(
        [ModelRequest.user_text_prompt("x")], None, ModelRequestParameters()
    )
    with misura_attese() as m:
        risposta = asyncio.run(entro_il_tempo(richiesta, 4.0, m, orologio=lambda: t[0]))
    assert risposta.parts[0].content == "ok"  # type: ignore[union-attr]
    assert m.secondi == 5.0 and m.tentativi_falliti == 1


def test_rifiuto_per_causa_non_letta_si_conta_una_volta() -> None:
    parte = RetryPromptPart(content=f"{RIFIUTO_CAUSA_NON_LETTA}: apri DOC-EML-001")
    assert rifiuti_del_validatore([ModelRequest(parts=[parte])]) == {"causa_non_letta": 1}


@pytest.mark.parametrize("codice", [401, 402, 403])
def test_credito_o_chiave_sono_errori_fatali(codice) -> None:
    e = ModelHTTPError(codice, "openrouter:m")
    assert errore_fatale(e)
    assert not errore_di_infrastruttura(e)  # non si ritenta: si ferma tutto


@pytest.mark.parametrize("codice", [400, 429, 503])
def test_altri_codici_non_sono_fatali(codice) -> None:
    assert not errore_fatale(ModelHTTPError(codice, "openrouter:m"))


def test_costo_risposte_somma_il_costo_di_openrouter() -> None:
    messaggi = [
        ModelRequest.user_text_prompt("q"),
        ModelResponse(parts=[TextPart("a")], provider_details={"cost": 0.001}),
        ModelResponse(parts=[TextPart("b")], provider_details={"cost": 0.002}),
    ]
    assert costo_risposte(messaggi) == pytest.approx(0.003)
    # senza costo nelle risposte (Gemini, modelli finti): non si sa, non zero
    assert costo_risposte([ModelResponse(parts=[TextPart("a")])]) is None
