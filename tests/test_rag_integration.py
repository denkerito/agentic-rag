import psycopg
import pytest
from psycopg import errors

from agentic_rag import config
from agentic_rag.rag.indexer import index_all
from agentic_rag.rag.search import search_chunks

pytestmark = pytest.mark.integration

EXPECTED_CHUNKS = 98


@pytest.fixture(scope="module")
def owner():
    if not config.GOOGLE_API_KEY:
        pytest.skip("GOOGLE_API_KEY non impostata")
    try:
        conn = psycopg.connect(config.DATABASE_URL, connect_timeout=3)
    except psycopg.Error:
        pytest.skip("database non raggiungibile")
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def indexed(owner):
    index_all(owner)
    return owner


def test_every_document_indexed_with_embeddings(indexed) -> None:
    total, with_emb = indexed.execute(
        "SELECT count(*), count(embedding) FROM documenti_chunks"
    ).fetchone()
    assert total == with_emb == EXPECTED_CHUNKS
    missing = indexed.execute(
        "SELECT count(*) FROM documenti d WHERE NOT EXISTS "
        "(SELECT 1 FROM documenti_chunks c WHERE c.doc_id = d.doc_id)"
    ).fetchone()[0]
    assert missing == 0


def test_reindex_is_idempotent(indexed) -> None:
    index_all(indexed)
    assert indexed.execute("SELECT count(*) FROM documenti_chunks").fetchone()[0] == EXPECTED_CHUNKS


def test_search_finds_nimbus_documents(indexed) -> None:
    hits = search_chunks(indexed, "aumento del canone software Nimbus", k=5)
    nimbus = {"CTR-001", "DOC-EML-001", "DOC-EML-002", "DOC-EML-003", "DOC-LET-001"}
    assert nimbus & {h.doc_id for h in hits}


def test_search_filters(indexed) -> None:
    by_supplier = search_chunks(indexed, "canone", k=10, fornitore_id="FOR-001")
    assert by_supplier
    ids = {
        r[0]
        for r in indexed.execute(
            "SELECT doc_id FROM documenti WHERE fornitore_id = 'FOR-001'"
        ).fetchall()
    }
    assert {h.doc_id for h in by_supplier} <= ids
    assert all(h.tipo == "email" for h in search_chunks(indexed, "canone", k=10, tipo="email"))


def test_agent_role_can_search_but_not_write(indexed) -> None:
    with psycopg.connect(config.DATABASE_URL_AGENT, connect_timeout=3) as agent:
        assert search_chunks(agent, "preavviso di rinnovo del contratto", k=3)
        with pytest.raises((errors.InsufficientPrivilege, errors.ReadOnlySqlTransaction)):
            agent.execute("DELETE FROM documenti_chunks")
