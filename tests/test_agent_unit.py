import csv

import pytest
from pydantic_ai import ModelRetry

from agentic_rag.agent.agent import check_risposta
from agentic_rag.agent.ids import ID_PATTERN, extract_ids
from agentic_rag.agent.output import Numero, Risposta
from agentic_rag.agent.sql_guard import SqlRejected, validate_select
from agentic_rag.config import DATA_DIR

REL = {"fatture", "v_margine_mensile", "documenti"}


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM fatture",
        "WITH x AS (SELECT * FROM v_margine_mensile) SELECT * FROM x",
        "SELECT mese FROM v_margine_mensile UNION ALL SELECT mese FROM v_margine_mensile",
        "SELECT id FROM fatture WHERE data >= '2025-01-01';",
    ],
)
def test_guard_accepts_selects(sql: str) -> None:
    assert validate_select(sql, REL)


@pytest.mark.parametrize(
    "sql",
    [
        "",
        "INSERT INTO fatture VALUES (1)",
        "UPDATE fatture SET totale = 0",
        "DELETE FROM fatture",
        "DROP TABLE fatture",
        "SELECT 1; DROP TABLE fatture",
        "SELECT pg_sleep(5)",
        "SELECT pg_read_file('/etc/passwd')",
        "SELECT * FROM pg_catalog.pg_user",
        "SELECT * FROM pg_shadow",
        "SELECT * FROM public.fatture",
        "SELECT * FROM fatture FOR UPDATE",
        "SELECT * INTO nuova FROM fatture",
        "SELECT set_config('a', 'b', false)",
        "SELEC broken",
        "SET ROLE postgres",
    ],
)
def test_guard_rejects(sql: str) -> None:
    with pytest.raises(SqlRejected):
        validate_select(sql, REL)


def test_id_pattern_matches_every_csv_id() -> None:
    ids: list[str] = []
    for name in (
        "fatture",
        "fatture_righe",
        "movimenti_bancari",
        "scritture_contabili",
        "scadenzario",
        "contratti",
        "clienti",
        "fornitori",
    ):
        with (DATA_DIR / "csv" / f"{name}.csv").open(encoding="utf-8", newline="") as f:
            ids += [r["id"] for r in csv.DictReader(f)]
    with (DATA_DIR / "documenti" / "index.csv").open(encoding="utf-8", newline="") as f:
        ids += [r["doc_id"] for r in csv.DictReader(f)]
    assert ids
    bad = [i for i in ids if not ID_PATTERN.fullmatch(i)]
    assert not bad, bad[:5]


def test_extract_ids() -> None:
    assert extract_ids("vedi FATT-P-2025-0001 e CTR-001, non XFATT-1") == {
        "FATT-P-2025-0001",
        "CTR-001",
    }


def _risposta(**kw) -> Risposta:
    base = {"conclusione": "c", "fonti": [], "confidenza": "alta", "causa_documentata": False}
    return Risposta(**{**base, **kw})


def test_validator_rejects_unseen_sources() -> None:
    with pytest.raises(ModelRetry, match="FATT-P-2025-9999"):
        check_risposta(_risposta(fonti=["FATT-P-2025-9999"]), {"FATT-P-2025-0001"})


def test_validator_rejects_number_without_sources() -> None:
    r = _risposta(numeri=[Numero(descrizione="costi", valore="10", fonti=[])])
    with pytest.raises(ModelRetry, match="senza fonti"):
        check_risposta(r, set())


def test_validator_requires_document_for_documented_cause() -> None:
    r = _risposta(fonti=["FATT-P-2025-0001"], causa_documentata=True)
    with pytest.raises(ModelRetry, match="documentale"):
        check_risposta(r, {"FATT-P-2025-0001"})


def test_validator_accepts_seen_sources() -> None:
    r = _risposta(
        numeri=[Numero(descrizione="canone", valore="5", fonti=["FATT-P-2025-0001"])],
        fonti=["FATT-P-2025-0001", "CTR-001"],
        causa_documentata=True,
    )
    check_risposta(r, {"FATT-P-2025-0001", "CTR-001"})
