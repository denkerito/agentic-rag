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
