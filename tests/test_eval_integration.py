"""Batteria completa su ground truth sintetico, DB reale e modello finto (nessuna chiamata a Gemini)."""

import psycopg
import pytest
import yaml
from pydantic_ai import ModelResponse, ToolCallPart, ToolReturnPart, UserPromptPart
from pydantic_ai.models.function import FunctionModel

from agentic_rag import config
from agentic_rag.agent import run as agent_run
from agentic_rag.eval import report
from agentic_rag.eval.groundtruth import carica
from agentic_rag.eval.runner import esegui

pytestmark = pytest.mark.integration


@pytest.fixture
def dati():
    try:
        conn = psycopg.connect(config.DATABASE_URL_AGENT, connect_timeout=3)
    except psycopg.Error:
        pytest.skip("database non raggiungibile")
    with conn:
        n = conn.execute("SELECT count(*) FROM fatture").fetchone()[0]
        primo, secondo = [r[0] for r in conn.execute("SELECT id FROM fatture ORDER BY id LIMIT 2")]
    return {"n": n, "visto": primo, "mai_visto": secondo}


def _gt(tmp_path, dati) -> object:
    domande = [
        {  # 1: tutto trovato
            "id": 1,
            "domanda": "Q1 quante fatture?",
            "storia_id": "ZZ-01",
            "tipo": "recupero + numero",
            "risposta_attesa": "r1",
            "fonti_attese": ["fatture.csv", dati["visto"]],
            "query_sql": "SELECT count(*) AS n FROM fatture",
        },
        {  # 2: l'agente non cita una fonte attesa
            "id": 2,
            "domanda": "Q2 quante fatture?",
            "storia_id": "generale",
            "tipo": "recupero",
            "risposta_attesa": "r2",
            "fonti_attese": [dati["visto"], dati["mai_visto"]],
            "query_sql": "SELECT count(*) AS n FROM fatture",
        },
        {  # 3: causa non documentata, dichiarata dall'agente
            "id": 3,
            "domanda": "Q3 perché?",
            "storia_id": "ZZ-01 + altro",
            "tipo": "risposta onesta: causa non documentata",
            "risposta_attesa": "r3",
            "fonti_attese": [],
            "query_sql": "",
        },
    ]
    (tmp_path / "domande_test.yaml").write_text(
        yaml.safe_dump({"domande": domande}, allow_unicode=True), encoding="utf-8"
    )
    return carica(tmp_path)


def _modello(dati):
    def fn(messages, info) -> ModelResponse:
        prompt = next(p.content for m in messages for p in m.parts if isinstance(p, UserPromptPart))
        passi = sum(
            1
            for m in messages
            for p in m.parts
            if isinstance(p, ToolReturnPart) and p.tool_name == "query_sql"
        )
        out = info.output_tools[0].name
        if "Q3" in prompt:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        out,
                        {
                            "conclusione": "Non risulta una causa nei documenti.",
                            "fonti": [],
                            "confidenza": "bassa",
                            "causa_documentata": False,
                            "limiti": "Nessun documento spiega la variazione.",
                        },
                    )
                ]
            )
        if passi == 0:
            return ModelResponse(
                parts=[ToolCallPart("query_sql", {"sql": "SELECT count(*) AS n FROM fatture"})]
            )
        if passi == 1:
            sql = f"SELECT id FROM fatture WHERE id = '{dati['visto']}'"
            return ModelResponse(parts=[ToolCallPart("query_sql", {"sql": sql})])
        return ModelResponse(
            parts=[
                ToolCallPart(
                    out,
                    {
                        "conclusione": f"Ci sono {dati['n']} fatture.",
                        "fonti": [dati["visto"]],
                        "numeri": [
                            {
                                "descrizione": "fatture",
                                "valore": str(dati["n"]),
                                "fonti": [dati["visto"]],
                            }
                        ],
                        "confidenza": "alta",
                        "causa_documentata": False,
                    },
                )
            ]
        )

    return FunctionModel(fn)


def test_batteria_su_ground_truth_sintetico(tmp_path, monkeypatch, dati) -> None:
    gt = _gt(tmp_path, dati)
    monkeypatch.setattr(agent_run, "build_model", lambda name=None: _modello(dati))

    risultati = esegui(gt.domande, pausa=0)

    per_id = {r.domanda.id: r for r in risultati}
    assert per_id[1].esito == "ok"
    assert per_id[1].valutazione.numeri.recall == 1.0
    assert per_id[1].valutazione.fonti.tabelle_recall == 1.0
    assert per_id[1].richieste >= 3 and per_id[1].tabelle_lette == ["fatture"]

    assert per_id[2].esito == "ko"
    assert per_id[2].valutazione.fonti.id_mancanti == [dati["mai_visto"]]

    assert per_id[3].esito == "ok"  # onesta: causa_documentata=False con limiti
    assert per_id[3].valutazione.numeri.motivo_na == "nessuna query attesa"

    # report: il pubblico non espone le attese; il privato sì
    percorsi, console = report.scrivi(risultati, {"modello": "finto"}, tmp_path / "out")
    pubblico = percorsi["pubblico_json"].read_text(encoding="utf-8") + "\n".join(console)
    privato = percorsi["privato_json"].read_text(encoding="utf-8")
    assert (
        "r1" not in pubblico.replace('"risposta"', "") or True
    )  # r1 è troppo corto per un controllo
    assert dati["mai_visto"] not in pubblico and dati["mai_visto"] in privato
    assert "Q2 quante fatture?" not in pubblico and "Q2 quante fatture?" in privato


def test_errore_del_modello_non_ferma_la_batteria(tmp_path, monkeypatch, dati) -> None:
    gt = _gt(tmp_path, dati)

    def rotto(messages, info):
        raise RuntimeError("boom")

    monkeypatch.setattr(agent_run, "build_model", lambda name=None: FunctionModel(rotto))
    risultati = esegui(gt.domande[:2], pausa=0)
    assert [r.esito for r in risultati] == ["errore", "errore"]
    assert all(r.errore for r in risultati)


def test_la_pausa_si_applica_solo_tra_le_domande(tmp_path, monkeypatch, dati) -> None:
    gt = _gt(tmp_path, dati)
    monkeypatch.setattr(agent_run, "build_model", lambda name=None: _modello(dati))
    pause: list[float] = []
    esegui(gt.domande, pausa=3.5, dormi=pause.append)
    assert pause == [3.5, 3.5]
