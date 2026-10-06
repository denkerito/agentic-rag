"""API end-to-end con DB reale e modello finto (nessuna chiamata a Gemini)."""

import asyncio
import inspect
import json
import time

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.pq import TransactionStatus
from pydantic_ai import ModelResponse, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import DeltaToolCall, FunctionModel

from agentic_rag import config
from agentic_rag.agent import run as agent_run
from agentic_rag.agent.ids import extract_ids
from agentic_rag.agent.tools import run_open
from agentic_rag.api import repository
from agentic_rag.api.app import create_app

pytestmark = pytest.mark.integration

PREFIX = "TEST-API "


@pytest.fixture(autouse=True)
def db_pulito():
    def clean() -> None:
        with psycopg.connect(config.DATABASE_URL, connect_timeout=3) as c:
            c.execute("DELETE FROM app.indagini WHERE domanda LIKE %s", (PREFIX + "%",))

    try:
        clean()
    except psycopg.Error:
        pytest.skip("database non raggiungibile o schema app mancante")
    yield
    clean()


def _modello(fn) -> FunctionModel:
    """FunctionModel che serve in streaming (come fa run_stream_events) le risposte di `fn`."""

    async def stream(messages, info):
        resp = fn(messages, info)
        if inspect.isawaitable(resp):
            resp = await resp
        for i, p in enumerate(resp.parts):
            yield {i: DeltaToolCall(name=p.tool_name, json_args=json.dumps(p.args))}

    return FunctionModel(fn, stream_function=stream)


def _risposta(fonti: list[str]) -> dict:
    return {"conclusione": "ok", "fonti": fonti, "confidenza": "alta", "causa_documentata": False}


def _script_con_scarto(monkeypatch) -> None:
    """query_sql -> risposta con fonte mai vista (scartata) -> risposta corretta."""
    calls = 0

    def fn(messages, info) -> ModelResponse:
        nonlocal calls
        calls += 1
        out = info.output_tools[0].name
        if calls == 1:
            sql = "SELECT id FROM fatture ORDER BY id LIMIT 2"
            return ModelResponse(parts=[ToolCallPart("query_sql", {"sql": sql})])
        if calls == 2:
            return ModelResponse(parts=[ToolCallPart(out, _risposta(["FATT-P-2025-9999"]))])
        visti: set[str] = set()
        for m in messages:
            for p in m.parts:
                if isinstance(p, ToolReturnPart) and p.tool_name == "query_sql":
                    visti |= extract_ids(str(p.content))
        return ModelResponse(parts=[ToolCallPart(out, _risposta(sorted(visti)))])

    monkeypatch.setattr(agent_run, "build_model", lambda name=None: _modello(fn))


def _leggi_sse(client: TestClient, url: str, **kw) -> list[tuple[str, int, dict]]:
    """Legge lo stream fino alla chiusura; ogni blocco (separato da riga vuota) è un evento."""
    out: list[tuple[str, int, dict]] = []
    with client.stream("GET", url, **kw) as r:
        assert r.status_code == 200
        campi: dict[str, str] = {}
        for line in [*r.iter_lines(), ""]:
            if line == "":
                if "data" in campi:
                    out.append((campi["event"], int(campi["id"]), json.loads(campi["data"])))
                campi = {}
            elif not line.startswith(":"):
                nome, _, valore = line.partition(":")
                campi[nome] = valore.strip()
    return out


def _attendi_stato(client: TestClient, id: str, stati: set[str], timeout: float = 15) -> dict:
    fine = time.time() + timeout
    while time.time() < fine:
        d = client.get(f"/indagini/{id}").json()
        if d["stato"] in stati:
            return d
        time.sleep(0.2)
    raise AssertionError(f"stato non raggiunto: {stati}")


def test_flusso_completo_replay_e_ripresa(monkeypatch) -> None:
    _script_con_scarto(monkeypatch)
    with TestClient(create_app()) as client:
        r = client.post("/indagini", json={"domanda": PREFIX + "margine"})
        assert r.status_code == 202
        id = r.json()["id"]

        eventi = _leggi_sse(client, f"/indagini/{id}/eventi")
        assert [e[0] for e in eventi] == [
            "tool_call",
            "tool_result",
            "risposta_scartata",
            "risposta",
        ]
        assert [e[1] for e in eventi] == [1, 2, 3, 4]
        result = eventi[1][2]
        assert result["n_righe"] == 2 and len(result["ids"]) == 2 and "righe" not in result
        assert "FATT-P-2025-9999" in eventi[2][2]["motivo"]

        dett = client.get(f"/indagini/{id}").json()
        assert dett["stato"] == "completata"
        assert dett["risposta"] == eventi[3][2]["risposta"]
        assert dett["utilizzo"]["requests"] == 3

        # rivisto dopo: replay completo e ripresa da Last-Event-ID
        assert len(_leggi_sse(client, f"/indagini/{id}/eventi")) == 4
        ripresi = _leggi_sse(client, f"/indagini/{id}/eventi", headers={"Last-Event-ID": "2"})
        assert [e[1] for e in ripresi] == [3, 4]
        assert any(i["id"] == id for i in client.get("/indagini").json())


def test_stop_interrompe_indagine(monkeypatch) -> None:
    async def lenta(messages, info) -> ModelResponse:
        await asyncio.sleep(30)
        raise AssertionError("non deve arrivare qui")

    monkeypatch.setattr(agent_run, "build_model", lambda name=None: _modello(lenta))
    with TestClient(create_app()) as client:
        id = client.post("/indagini", json={"domanda": PREFIX + "lenta"}).json()["id"]
        _attendi_stato(client, id, {"in_corso"})
        assert client.post(f"/indagini/{id}/stop").status_code == 202
        dett = _attendi_stato(client, id, {"interrotta"})
        assert dett["risposta"] is None
        assert [e[0] for e in _leggi_sse(client, f"/indagini/{id}/eventi")] == ["interrotta"]
        assert client.post(f"/indagini/{id}/stop").status_code == 409


def test_errore_del_modello_diventa_evento_errore(monkeypatch) -> None:
    def rotto(messages, info) -> ModelResponse:
        raise RuntimeError("boom")

    monkeypatch.setattr(agent_run, "build_model", lambda name=None: _modello(rotto))
    with TestClient(create_app()) as client:
        id = client.post("/indagini", json={"domanda": PREFIX + "errore"}).json()["id"]
        eventi = _leggi_sse(client, f"/indagini/{id}/eventi")
        assert [e[0] for e in eventi] == ["errore"]
        assert "boom" in eventi[0][2]["messaggio"]
        assert client.get(f"/indagini/{id}").json()["stato"] == "fallita"


def test_indagini_orfane_vengono_interrotte_all_avvio() -> None:
    with repository.connect() as conn:
        id = repository.crea_indagine(conn, PREFIX + "orfana", "x")
        repository.segna_in_corso(conn, id)
    with TestClient(create_app()) as client:
        assert client.get(f"/indagini/{id}").json()["stato"] == "interrotta"
        assert [e[0] for e in _leggi_sse(client, f"/indagini/{id}/eventi")] == ["interrotta"]


def test_validazione_e_404() -> None:
    with TestClient(create_app()) as client:
        assert client.post("/indagini", json={"domanda": "   "}).status_code == 422
        inesistente = "00000000-0000-0000-0000-000000000000"
        assert client.get(f"/indagini/{inesistente}").status_code == 404
        assert client.get(f"/indagini/{inesistente}/eventi").status_code == 404
        assert client.post(f"/indagini/{inesistente}/stop").status_code == 404


def test_agent_ro_non_vede_lo_storico() -> None:
    conn = psycopg.connect(config.DATABASE_URL_AGENT, connect_timeout=3)
    with conn, pytest.raises(psycopg.Error):
        conn.execute("SELECT * FROM app.indagini")


def test_sessione_agente_non_resta_in_transazione(monkeypatch) -> None:
    """agent_ro ha idle_in_transaction_session_timeout=30s: nessuna transazione aperta in attesa."""
    monkeypatch.setattr(agent_run, "build_model", lambda name=None: "test")
    _, deps = agent_run.open_session()
    try:
        assert deps.conn.info.transaction_status == TransactionStatus.IDLE
        run_open(deps, "CTR-001", 0)
        assert deps.conn.info.transaction_status == TransactionStatus.IDLE
    finally:
        deps.conn.close()
