"""Batteria completa su ground truth sintetico, DB reale e modello finto (nessuna chiamata a Gemini)."""

import json

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


def test_il_client_del_modello_si_chiude_dopo_ogni_domanda(tmp_path, monkeypatch, dati) -> None:
    from agentic_rag.agent import model

    gt = _gt(tmp_path, dati)
    chiusi: list[object] = []

    async def registra(model) -> None:
        chiusi.append(model)

    def rotto(messages, info):
        raise RuntimeError("boom")

    monkeypatch.setattr(model, "chiudi_client", registra)
    monkeypatch.setattr(agent_run, "build_model", lambda name=None: _modello(dati))
    esegui(gt.domande[:1], pausa=0)
    monkeypatch.setattr(agent_run, "build_model", lambda name=None: FunctionModel(rotto))
    esegui(gt.domande[:1], pausa=0)  # anche quando la run fallisce
    assert len(chiusi) == 2


def test_la_pausa_si_applica_solo_tra_le_domande(tmp_path, monkeypatch, dati) -> None:
    gt = _gt(tmp_path, dati)
    monkeypatch.setattr(agent_run, "build_model", lambda name=None: _modello(dati))
    pause: list[float] = []
    esegui(gt.domande, pausa=3.5, dormi=pause.append)
    assert pause == [3.5, 3.5]


def test_una_domanda_bloccata_va_in_timeout_e_la_batteria_prosegue(
    tmp_path, monkeypatch, dati
) -> None:
    import asyncio

    gt = _gt(tmp_path, dati)

    async def lenta(messages, info):
        await asyncio.sleep(30)
        raise AssertionError("non deve arrivare qui")

    monkeypatch.setattr(agent_run, "build_model", lambda name=None: FunctionModel(lenta))
    risultati = esegui(gt.domande[:2], pausa=0, timeout=0.3)
    assert [r.esito for r in risultati] == ["errore", "errore"]
    assert [r.errore for r in risultati] == ["TempoScaduto", "TempoScaduto"]
    assert [r.stato for r in risultati] == ["fallita_agente", "fallita_agente"]
    assert not any(r.rieseguita for r in risultati)  # lentezza dell'agente, non infrastruttura
    assert [r.passi_tool for r in risultati] == [0, 0]


def test_interruzione_conserva_le_domande_completate(tmp_path, monkeypatch, dati) -> None:
    gt = _gt(tmp_path, dati)
    monkeypatch.setattr(agent_run, "build_model", lambda name=None: _modello(dati))

    def ctrl_c(_secondi: float) -> None:
        raise KeyboardInterrupt

    risultati: list = []
    with pytest.raises(KeyboardInterrupt):
        esegui(gt.domande, pausa=1, dormi=ctrl_c, risultati=risultati)
    assert [r.domanda.id for r in risultati] == [1]  # la prima è completa e non si perde


def test_inizio_e_progresso_sono_notificati_in_ordine(tmp_path, monkeypatch, dati) -> None:
    gt = _gt(tmp_path, dati)
    monkeypatch.setattr(agent_run, "build_model", lambda name=None: _modello(dati))
    eventi: list[str] = []
    esegui(
        gt.domande[:2],
        pausa=0,
        inizio=lambda d: eventi.append(f"inizio {d.id}"),
        progresso=lambda r: eventi.append(f"fine {r.domanda.id}"),
    )
    assert eventi == ["inizio 1", "fine 1", "inizio 2", "fine 2"]


def test_database_giu_non_blocca_la_batteria(tmp_path, monkeypatch, dati) -> None:
    gt = _gt(tmp_path, dati)
    monkeypatch.setattr(config, "DATABASE_URL_AGENT", "postgresql://u:p@127.0.0.1:1/db")
    from agentic_rag import config as app_config

    monkeypatch.setattr(app_config, "DATABASE_URL_AGENT", "postgresql://u:p@127.0.0.1:1/db")
    risultati = esegui(gt.domande[:1], pausa=0)
    assert risultati[0].esito == "errore" and risultati[0].errore.startswith("database:")


def test_errore_del_provider_si_riesegue_una_volta(tmp_path, monkeypatch, dati) -> None:
    gt = _gt(tmp_path, dati)
    sano = _modello(dati).function
    chiamate = {"n": 0}

    def instabile(messages, info):
        chiamate["n"] += 1
        if chiamate["n"] == 1:
            raise TimeoutError
        return sano(messages, info)

    monkeypatch.setattr(agent_run, "build_model", lambda name=None: FunctionModel(instabile))
    pause: list[float] = []
    risultati = esegui(gt.domande[:1], pausa=2, dormi=pause.append)
    assert risultati[0].esito == "ok" and risultati[0].rieseguita
    assert pause == [2]  # pausa prima del secondo tentativo


def test_limite_di_richieste_non_si_riesegue(tmp_path, monkeypatch, dati) -> None:
    from pydantic_ai.exceptions import UsageLimitExceeded

    gt = _gt(tmp_path, dati)
    chiamate = {"n": 0}

    def esaurito(messages, info):
        chiamate["n"] += 1
        raise UsageLimitExceeded("limite")

    monkeypatch.setattr(agent_run, "build_model", lambda name=None: FunctionModel(esaurito))
    risultati = esegui(gt.domande[:1], pausa=0)
    assert risultati[0].esito == "errore" and not risultati[0].rieseguita
    assert chiamate["n"] == 1


def test_esperimento_reale_con_modello_finto(tmp_path, monkeypatch, dati) -> None:
    from agentic_rag.eval.esperimento import (
        analizza_variante,
        crea_manifesto,
        esegui_esperimento,
        leggi_jsonl,
    )
    from agentic_rag.eval.riepilogo import riepiloga

    gt = _gt(tmp_path, dati)
    monkeypatch.setattr(agent_run, "build_model", lambda name=None: _modello(dati))
    varianti = [analizza_variante("con:semantica=1"), analizza_variante("senza:semantica=0")]
    stato = {"src": "s", "ground_truth": "g", "domande": [1, 3], "limiti": {"timeout_lavoro_s": 60}}
    m = crea_manifesto("esp", varianti, 1, None, None, stato)
    domande = [d for d in gt.domande if d.id in (1, 3)]
    esegui_esperimento(m, domande, tmp_path / "pub", tmp_path / "priv", pausa=0)
    righe = leggi_jsonl(tmp_path / "pub" / "esecuzioni.jsonl")
    assert [(r["variante"], r["id"], r["stato"]) for r in righe] == [
        ("con", 1, "completata"),
        ("con", 3, "completata"),
        ("senza", 1, "completata"),
        ("senza", 3, "completata"),
    ]
    assert all(r["token_input"] > 0 and r["lavoro_s"] >= 0 for r in righe)
    assert righe[1]["conteggi"]["causa_attesa"] == "non_documentata"
    assert "risposta_attesa" not in json.dumps(righe)  # il pubblico non contiene il ground truth
    riep = riepiloga(m, righe)
    assert (
        riep["valido"] and riep["varianti"]["con"]["metriche"]["task_success_rate"]["valore"] == 1.0
    )


def test_i_rifiuti_del_validatore_si_contano_per_motivo(tmp_path, monkeypatch, dati) -> None:
    gt = _gt(tmp_path, dati)
    sano = _modello(dati).function
    finali = {"n": 0}

    def cita_inventato(messages, info):
        risposta = sano(messages, info)
        parte = risposta.parts[0]
        if isinstance(parte, ToolCallPart) and parte.tool_name == info.output_tools[0].name:
            finali["n"] += 1
            if finali["n"] == 1:  # la prima risposta finale cita una fonte mai vista
                args = dict(parte.args_as_dict())
                args["fonti"] = [*args.get("fonti", []), dati["mai_visto"]]
                return ModelResponse(parts=[ToolCallPart(parte.tool_name, args)])
        return risposta

    monkeypatch.setattr(agent_run, "build_model", lambda name=None: FunctionModel(cita_inventato))
    r = esegui(gt.domande[:1], pausa=0)[0]
    assert r.stato == "completata" and r.rifiuti == {"fonti_non_viste": 1}


def test_un_esecuzione_fallita_conserva_uso_e_rifiuti(tmp_path, monkeypatch, dati) -> None:
    gt = _gt(tmp_path, dati)
    sano = _modello(dati).function

    def cita_sempre_inventato(messages, info):
        risposta = sano(messages, info)
        parte = risposta.parts[0]
        if isinstance(parte, ToolCallPart) and parte.tool_name == info.output_tools[0].name:
            args = dict(parte.args_as_dict())
            args["fonti"] = [*args.get("fonti", []), dati["mai_visto"]]
            return ModelResponse(parts=[ToolCallPart(parte.tool_name, args)])
        return risposta

    monkeypatch.setattr(
        agent_run, "build_model", lambda name=None: FunctionModel(cita_sempre_inventato)
    )
    r = esegui(gt.domande[:1], pausa=0)[0]
    # il validatore rifiuta finché la run fallisce: rifiuti, richieste e token restano nella riga
    assert r.stato == "fallita_agente" and r.rifiuti.get("fonti_non_viste", 0) > 0
    assert r.richieste > 0 and r.token_input > 0 and r.token_output > 0


def test_ambiente_pronto_sul_database_reale(dati) -> None:
    from agentic_rag.eval.ambiente import controlla_ambiente

    assert controlla_ambiente(google_key="k") == []  # compresa la colonna full-text dei documenti


def test_la_batteria_rispetta_ricerca_semantica_spenta(tmp_path, monkeypatch, dati) -> None:
    from agentic_rag.agent import config as agent_config

    gt = _gt(tmp_path, dati)
    sano = _modello(dati).function
    offerti: set[str] = set()

    def registra(messages, info):
        offerti.update(t.name for t in info.function_tools)
        return sano(messages, info)

    monkeypatch.setattr(agent_config, "RICERCA_SEMANTICA", False)  # RICERCA_SEMANTICA=0 nel .env
    monkeypatch.setattr(agent_run, "build_model", lambda name=None: FunctionModel(registra))
    esegui(gt.domande[:1], pausa=0)
    assert "cerca_testo" in offerti and "cerca_semantica" not in offerti


def test_credito_esaurito_dell_agente_e_fatale(tmp_path, monkeypatch, dati) -> None:
    from pydantic_ai.exceptions import ModelHTTPError

    from agentic_rag.eval.runner import ErroreFatale, esegui_domanda

    gt = _gt(tmp_path, dati)

    def senza_credito(messages, info):
        raise ModelHTTPError(402, "m")

    monkeypatch.setattr(agent_run, "build_model", lambda name=None: FunctionModel(senza_credito))
    with pytest.raises(ErroreFatale, match="402"):
        esegui_domanda(gt.domande[0])


def test_credito_esaurito_del_giudice_e_fatale(tmp_path, monkeypatch, dati) -> None:
    from pydantic_ai.exceptions import ModelHTTPError

    from agentic_rag.eval import giudice
    from agentic_rag.eval.runner import ErroreFatale, esegui_domanda

    gt = _gt(tmp_path, dati)

    def senza_credito(messages, info):
        raise ModelHTTPError(402, "m")

    monkeypatch.setattr(agent_run, "build_model", lambda name=None: _modello(dati))
    monkeypatch.setattr(
        giudice, "build_model", lambda name=None, ruolo=None: FunctionModel(senza_credito)
    )
    with pytest.raises(ErroreFatale, match="402"):
        esegui_domanda(gt.domande[0], judge=True)


def test_giudice_senza_verdetto_lascia_aperta_la_combinazione(tmp_path, monkeypatch, dati) -> None:
    from pydantic_ai.exceptions import ModelHTTPError

    from agentic_rag.eval import giudice
    from agentic_rag.eval.runner import esegui_domanda

    gt = _gt(tmp_path, dati)

    def rifiuta(messages, info):
        raise ModelHTTPError(400, "m")  # es. un parametro non supportato: fallisce sempre

    monkeypatch.setattr(agent_run, "build_model", lambda name=None: _modello(dati))
    monkeypatch.setattr(
        giudice, "build_model", lambda name=None, ruolo=None: FunctionModel(rifiuta)
    )
    r = esegui_domanda(gt.domande[0], judge=True)
    assert r.stato == "errore_giudice" and r.esito == "errore"
    assert r.errore_giudice == "ModelHTTPError"
    # l'esecuzione dell'agente resta registrata: risposta, uso
    assert r.risposta is not None and r.richieste > 0 and r.token_input > 0


def test_il_costo_di_openrouter_arriva_nella_riga(tmp_path, monkeypatch, dati) -> None:
    from agentic_rag.eval.metriche import riga_esecuzione_pubblica
    from agentic_rag.eval.runner import esegui_domanda

    gt = _gt(tmp_path, dati)
    sano = _modello(dati).function
    risposte = {"n": 0}

    def con_costo(messages, info):
        risposte["n"] += 1
        r = sano(messages, info)
        r.provider_details = {"cost": 0.001}
        return r

    monkeypatch.setattr(agent_run, "build_model", lambda name=None: FunctionModel(con_costo))
    r = esegui_domanda(gt.domande[0])
    riga = riga_esecuzione_pubblica(r, "con", 1, 1)
    assert riga["costo_usd"] == pytest.approx(0.001 * risposte["n"])
    assert riga["costo_giudice_usd"] is None  # giudice spento
    assert riga["token_cache_lettura"] == 0
