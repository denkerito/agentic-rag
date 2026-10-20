import re
from decimal import Decimal

import psycopg
import pytest
from pydantic_ai import ModelRetry

from agentic_rag import config
from agentic_rag.agent import config as agent_config
from agentic_rag.agent.deps import AgentDeps, list_relations
from agentic_rag.agent.schema_prompt import build_schema_ddl
from agentic_rag.agent.tools import run_elenco, run_open, run_query, run_testo

pytestmark = pytest.mark.integration


@pytest.fixture
def owner():
    try:
        conn = psycopg.connect(config.DATABASE_URL, connect_timeout=3)
    except psycopg.Error:
        pytest.skip("database non raggiungibile")
    yield conn
    conn.close()


@pytest.fixture
def deps():
    try:
        conn = psycopg.connect(config.DATABASE_URL_AGENT, connect_timeout=3)
    except psycopg.Error:
        pytest.skip("database non raggiungibile")
    yield AgentDeps(conn=conn, relations=list_relations(conn))
    conn.close()


def test_margin_view_reconciles_with_ledger(owner) -> None:
    months = owner.execute("SELECT count(*) FROM v_margine_mensile").fetchone()[0]
    assert months == 12
    wrong = owner.execute(
        "SELECT count(*) FROM v_margine_mensile WHERE margine <> ricavi - costi"
    ).fetchone()[0]
    assert wrong == 0
    ricavi, costi = owner.execute(
        "SELECT sum(avere - dare) FILTER (WHERE p.tipo = 'Ricavi'), "
        "sum(dare - avere) FILTER (WHERE p.tipo = 'Costi') "
        "FROM scritture_contabili s JOIN piano_dei_conti p ON p.codice = s.conto_codice"
    ).fetchone()
    v_ricavi, v_costi = owner.execute(
        "SELECT sum(ricavi), sum(costi) FROM v_margine_mensile"
    ).fetchone()
    assert (ricavi, costi) == (v_ricavi, v_costi)


def test_monthly_view_exposes_citable_sources(deps) -> None:
    res = run_query(deps, "SELECT fonti FROM v_economico_mensile WHERE mese = '2025-08-01'")
    assert res["n_righe"] > 0
    assert deps.seen_ids


def test_query_sql_returns_strings_for_decimals_and_registers_ids(deps) -> None:
    res = run_query(deps, "SELECT id, totale FROM fatture ORDER BY id LIMIT 2")
    assert res["colonne"] == ["id", "totale"]
    assert all(isinstance(r[1], str) and Decimal(r[1]) for r in res["righe"])
    assert {r[0] for r in res["righe"]} <= deps.seen_ids
    assert deps.trace[-1]["kind"] == "sql"


def test_query_sql_truncates_rows_and_cells(deps) -> None:
    res = run_query(deps, "SELECT * FROM scritture_contabili")
    assert res["troncato"] and res["n_righe"] == agent_config.SQL_MAX_ROWS
    res = run_query(deps, "SELECT repeat('x', 5000) AS t")
    assert len(res["righe"][0][0]) <= agent_config.SQL_MAX_CELL_CHARS + 1


def test_query_sql_errors_become_retries(deps) -> None:
    with pytest.raises(ModelRetry):
        run_query(deps, "SELECT colonna_inesistente FROM fatture")
    with pytest.raises(ModelRetry):
        run_query(deps, "DELETE FROM fatture")
    # la connessione resta utilizzabile dopo un errore
    assert run_query(deps, "SELECT 1 AS x")["righe"] == [[1]]


def test_database_blocks_writes_even_without_guard(deps) -> None:
    with pytest.raises(psycopg.Error):
        deps.conn.execute("DELETE FROM fatture")


def test_apri_documento(deps) -> None:
    doc = run_open(deps, "CTR-001", 0)
    assert doc["doc_id"] == "CTR-001" and doc["contenuto"]
    assert "CTR-001" in deps.seen_ids and deps.aperti == {"CTR-001"}
    with pytest.raises(ModelRetry):
        run_open(deps, "DOC-XXX-999", 0)


def test_schema_prompt_includes_comments_and_views(deps) -> None:
    ddl = build_schema_ddl(deps.conn)
    assert "VISTA v_margine_mensile" in ddl and "TABELLA fatture" in ddl
    assert "Positivo = entrata" in ddl
    assert "embedding" not in ddl


def test_schema_prompt_lists_values_of_enum_columns(deps) -> None:
    ddl = build_schema_ddl(deps.conn)
    for rel in ("v_economico", "v_economico_mensile"):
        blocco = ddl.split(f"-- VISTA {rel}:")[1].split("\n\n")[0]
        assert "'Costi'" in blocco and "'Ricavi'" in blocco


def test_enum_comments_match_check_constraints(owner) -> None:
    """Ogni valore di un CHECK (col IN (...)) deve comparire nel commento della colonna."""
    rows = owner.execute(
        "SELECT k.conrelid::regclass::text, a.attname, pg_get_constraintdef(k.oid), "
        "       col_description(c.oid, a.attnum) "
        "FROM pg_constraint k "
        "JOIN pg_class c ON c.oid = k.conrelid "
        "JOIN pg_attribute a ON a.attrelid = k.conrelid AND a.attnum = k.conkey[1] "
        "WHERE k.contype = 'c' AND cardinality(k.conkey) = 1 "
        "AND pg_get_constraintdef(k.oid) LIKE '%ANY (ARRAY[%' "
        "AND c.relnamespace = 'public'::regnamespace"
    ).fetchall()
    assert rows, "nessun CHECK enumerato trovato"
    for tabella, colonna, definizione, commento in rows:
        for valore in re.findall(r"'([^']+)'::text", definizione):
            assert commento and f"'{valore}'" in commento, f"{tabella}.{colonna}: manca '{valore}'"


def _testo(deps, query: str, k: int = 5, **filtri):
    base = dict.fromkeys(("tipo", "data_da", "data_a", "fornitore_id", "cliente_id"))
    f = {**base, **filtri}
    return run_testo(
        deps, query, k, f["tipo"], f["data_da"], f["data_a"], f["fornitore_id"], f["cliente_id"]
    )


def _elenco(deps, pagina: int = 1, **filtri):
    base = dict.fromkeys(("tipo", "data_da", "data_a", "fornitore_id", "cliente_id"))
    f = {**base, **filtri}
    return run_elenco(
        deps, f["tipo"], f["data_da"], f["data_a"], f["fornitore_id"], f["cliente_id"], pagina
    )


def test_cerca_testo_riconosce_le_forme_flesse(deps) -> None:
    singolare = _testo(deps, "canone", k=8)
    plurale = _testo(deps, "canoni", k=8)
    assert singolare["totale"] > 0 and plurale["totale"] == singolare["totale"]
    r = singolare["risultati"][0]
    assert set(r) == {"doc_id", "titolo", "tipo", "data", "frammenti"} and "«" in r["frammenti"]
    assert {x["doc_id"] for x in singolare["risultati"]} <= deps.seen_ids
    assert deps.aperti == set()  # trovato da una ricerca: citabile, non letto


def test_cerca_testo_or_e_filtri(deps) -> None:
    nimbus = _testo(deps, "Nimbus", k=8)
    alternative = _testo(deps, "Nimbus or locazione", k=8)
    assert alternative["totale"] > nimbus["totale"] > 0
    filtrato = _testo(deps, "Nimbus or locazione", k=8, fornitore_id="FOR-001")
    assert 0 < filtrato["totale"] < alternative["totale"]
    assert len(_testo(deps, "Nimbus", k=1)["risultati"]) == 1


def test_cerca_testo_senza_corrispondenze_lo_dichiara(deps) -> None:
    res = _testo(deps, "zzzparolainesistente")
    assert res["totale"] == 0 and res["risultati"] == [] and "sinonimi" in res["nota"]


def test_cerca_testo_rifiuta_query_senza_termini(deps) -> None:
    with pytest.raises(ModelRetry, match="termini utili"):
        _testo(deps, "il della")


def test_elenca_documenti_pagina_e_non_rende_citabile(deps) -> None:
    per_pagina = agent_config.ELENCO_PER_PAGINA
    prima = _elenco(deps)
    totale = prima["totale"]
    assert totale > per_pagina and len(prima["documenti"]) == per_pagina
    assert prima["pagine"] == -(-totale // per_pagina)
    ultima = _elenco(deps, pagina=prima["pagine"])
    assert len(ultima["documenti"]) == totale - per_pagina * (prima["pagine"] - 1)
    oltre = _elenco(deps, pagina=prima["pagine"] + 1)
    assert oltre["documenti"] == [] and "nota" in oltre
    assert deps.seen_ids == set() and deps.aperti == set()  # visto solo per titolo: va aperto


def test_elenca_documenti_filtra_per_controparte(deps) -> None:
    res = _elenco(deps, fornitore_id="FOR-001")
    assert res["totale"] > 0
    assert all(d["fornitore_id"] == "FOR-001" and d["controparte"] for d in res["documenti"])
    date = [d["data"] for d in res["documenti"]]
    assert date == sorted(date)


def test_documenti_si_leggono_solo_con_i_tool(deps) -> None:
    assert "documenti" not in deps.relations and "documenti_chunks" not in deps.relations
    with pytest.raises(ModelRetry, match="Relazione non ammessa"):
        run_query(deps, "SELECT contenuto FROM documenti")
    assert "TABELLA documenti" not in build_schema_ddl(deps.conn)
