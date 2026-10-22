import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from agentic_rag.agent import config as agent_config
from agentic_rag.agent.output import Risposta
from agentic_rag.eval import giudice


def test_il_giudice_usa_judge_model_senza_temperatura(monkeypatch) -> None:
    visti: dict = {}

    def rispondi(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        visti["settings"] = info.model_settings
        nome = info.output_tools[0].name
        return ModelResponse(
            parts=[ToolCallPart(nome, {"verdetto": "corretta", "motivazione": "m"})]
        )

    def finto(name=None, ruolo="agente"):
        visti["name"], visti["ruolo"] = name, ruolo
        return FunctionModel(rispondi)

    monkeypatch.setattr(giudice, "build_model", finto)
    risposta = Risposta(conclusione="c", fonti=[], confidenza="alta", causa_documentata=False)
    g = giudice.giudica("Q", "attesa", risposta)
    assert g.verdetto == "corretta"
    assert visti["name"] == agent_config.JUDGE_MODEL and visti["ruolo"] == "giudice"
    # i modelli con ragionamento rifiutano temperature diverse dal default
    assert (visti["settings"] or {}).get("temperature") is None


def _registra_chiusure(monkeypatch) -> list:
    from agentic_rag.agent import model

    chiusi: list = []

    async def registra(m) -> None:
        chiusi.append(m)

    monkeypatch.setattr(model, "chiudi_client", registra)
    return chiusi


def test_il_giudice_chiude_il_suo_client(monkeypatch) -> None:
    # nel suo ciclo: altrimenti il client lo chiude il garbage collector nel ciclo di un'altra
    # domanda (RuntimeError: Event loop is closed)
    def rispondi(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        nome = info.output_tools[0].name
        return ModelResponse(
            parts=[ToolCallPart(nome, {"verdetto": "corretta", "motivazione": "m"})]
        )

    modello = FunctionModel(rispondi)
    monkeypatch.setattr(giudice, "build_model", lambda name=None, ruolo="agente": modello)
    chiusi = _registra_chiusure(monkeypatch)
    risposta = Risposta(conclusione="c", fonti=[], confidenza="alta", causa_documentata=False)
    assert giudice.giudica("Q", "attesa", risposta).verdetto == "corretta"
    assert chiusi == [modello]


def test_il_giudice_chiude_il_client_anche_se_la_run_fallisce(monkeypatch) -> None:
    def rotto(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        raise RuntimeError("boom")

    modello = FunctionModel(rotto)
    monkeypatch.setattr(giudice, "build_model", lambda name=None, ruolo="agente": modello)
    chiusi = _registra_chiusure(monkeypatch)
    risposta = Risposta(conclusione="c", fonti=[], confidenza="alta", causa_documentata=False)
    with pytest.raises(RuntimeError, match="boom"):
        giudice.giudica("Q", "attesa", risposta)
    assert chiusi == [modello]
