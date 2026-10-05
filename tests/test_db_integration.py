import psycopg
import pytest
from psycopg import errors

from agentic_rag import config

pytestmark = pytest.mark.integration

EXPECTED = {
    "clienti": 7, "fornitori": 18, "piano_dei_conti": 34, "contratti": 10, "fatture": 295,
    "fatture_righe": 379, "movimenti_bancari": 311, "scritture_contabili": 1675,
    "scadenzario": 57, "documenti": 62,
}  # fmt: skip


@pytest.fixture(scope="module")
def owner():
    try:
        conn = psycopg.connect(config.DATABASE_URL, connect_timeout=3)
    except psycopg.Error:
        pytest.skip("database non raggiungibile")
    yield conn
    conn.close()


@pytest.fixture
def agent():
    try:
        conn = psycopg.connect(config.DATABASE_URL_AGENT, connect_timeout=3)
    except psycopg.Error:
        pytest.skip("database non raggiungibile")
    yield conn
    conn.close()


def test_row_counts(owner) -> None:
    for table, n in EXPECTED.items():
        assert owner.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == n, table


def test_transactions_balanced(owner) -> None:
    bad = owner.execute(
        "SELECT count(*) FROM (SELECT transazione_id FROM scritture_contabili "
        "GROUP BY 1 HAVING SUM(dare) <> SUM(avere)) t"
    ).fetchone()[0]
    assert bad == 0


def test_invoice_totals_match_lines(owner) -> None:
    bad = owner.execute(
        "SELECT count(*) FROM fatture f WHERE imponibile <> "
        "(SELECT SUM(imponibile) FROM fatture_righe WHERE fattura_id = f.id)"
    ).fetchone()[0]
    assert bad == 0


def test_duplicate_invoice_number_preserved(owner) -> None:
    n = owner.execute("SELECT count(*) FROM fatture WHERE numero = 'FT-2025-1089'").fetchone()[0]
    assert n == 2


def test_embedding_roundtrip(owner) -> None:
    vec = "[" + ",".join(["0.1"] * config.EMBEDDING_DIM) + "]"
    with owner.transaction(force_rollback=True):
        owner.execute(
            "INSERT INTO documenti_chunks (doc_id, chunk_index, testo, embedding) "
            "VALUES ('CTR-001', 999, 't', %s)",
            (vec,),
        )
        row = owner.execute(
            "SELECT doc_id FROM documenti_chunks ORDER BY embedding <=> %s::vector LIMIT 1",
            (vec,),
        ).fetchone()
    assert row[0] == "CTR-001"


def test_agent_can_select(agent) -> None:
    assert agent.execute("SELECT count(*) FROM fatture").fetchone()[0] == 295


@pytest.mark.parametrize(
    "stmt",
    [
        "INSERT INTO clienti (id) VALUES ('X')",
        "UPDATE fatture SET totale = 0",
        "DELETE FROM fatture",
        "TRUNCATE fatture",
        "DROP TABLE fatture",
        "CREATE TABLE x (a int)",
        "CREATE TEMP TABLE x (a int)",
    ],
)
def test_agent_cannot_write(agent, stmt: str) -> None:
    with pytest.raises((errors.InsufficientPrivilege, errors.ReadOnlySqlTransaction)):
        agent.execute(stmt)


def test_agent_statement_timeout(agent) -> None:
    with pytest.raises(errors.QueryCanceled):
        agent.execute("SELECT pg_sleep(15)")
