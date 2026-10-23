"""Indicizzazione e ricerca semantica sul DB reale.

L'indicizzatore si verifica con embedding finti dentro una transazione annullata: nessuna quota Gemini
consumata e l'indice usato dall'agente non si tocca. Solo le ricerche e una prova del percorso batch
chiamano l'API vera (circa 6 richieste per corsa). L'indice si costruisce con
`python -m agentic_rag.rag.indexer`.
"""

import hashlib

import psycopg
import pytest
from psycopg import errors

from agentic_rag import config
from agentic_rag.rag.embeddings import embed_documents
from agentic_rag.rag.indexer import index_all
from agentic_rag.rag.search import search_chunks

pytestmark = pytest.mark.integration

EXPECTED_CHUNKS = 98
CONTENUTO_INDICE = (
    "SELECT doc_id, chunk_index, testo, embedding::text FROM documenti_chunks "
    "ORDER BY doc_id, chunk_index"
)
SENZA_CHUNK = (
    "SELECT count(*) FROM documenti d "
    "WHERE NOT EXISTS (SELECT 1 FROM documenti_chunks c WHERE c.doc_id = d.doc_id)"
)


def _impronta(conn: psycopg.Connection) -> str:
    righe = conn.execute(CONTENUTO_INDICE).fetchall()  # type: ignore[arg-type]
    return hashlib.sha256(repr(righe).encode()).hexdigest()


class EmbedFinti:
    """Vettori deterministici ricavati dal testo; conta i testi ricevuti."""

    def __init__(self) -> None:
        self.testi = 0

    def __call__(self, testi: list[str]) -> list[list[float]]:
        self.testi += len(testi)
        out = []
        for t in testi:
            seme = hashlib.sha256(t.encode()).digest()
            out.append([seme[i % len(seme)] / 255 for i in range(config.EMBEDDING_DIM)])
        return out


@pytest.fixture(scope="module")
def db():
    try:
        conn = psycopg.connect(config.DATABASE_URL, connect_timeout=3, autocommit=True)
    except psycopg.Error:
        pytest.skip("database non raggiungibile")
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def impronta_vera(db) -> str:
    """L'indice vero prima dei test dell'indicizzatore: a fine modulo deve essere identico."""
    return _impronta(db)


@pytest.fixture
def isolato(db, impronta_vera):
    # index_all apre una transazione che qui diventa un savepoint: alla fine tutto si annulla
    with db.transaction(force_rollback=True):
        yield db


@pytest.fixture(scope="module")
def indexed(db):
    """L'indice vero, così com'è: i test non lo ricostruiscono (costerebbe circa 100 embedding)."""
    if not config.GOOGLE_API_KEY:
        pytest.skip("GOOGLE_API_KEY non impostata")
    totale, con_embedding = db.execute(
        "SELECT count(*), count(embedding) FROM documenti_chunks"
    ).fetchone()
    if totale != EXPECTED_CHUNKS or con_embedding != totale:
        pytest.skip("indice assente o incompleto: python -m agentic_rag.rag.indexer")
    return db


# --- indicizzatore, con embedding finti -----------------------------------------------------------


def test_index_all_un_chunk_per_testo_con_embedding(isolato) -> None:
    finti = EmbedFinti()
    chunks = index_all(isolato, embed=finti)
    totale, con_embedding = isolato.execute(
        "SELECT count(*), count(embedding) FROM documenti_chunks"
    ).fetchone()
    assert len(chunks) == finti.testi == totale == con_embedding == EXPECTED_CHUNKS
    assert isolato.execute(SENZA_CHUNK).fetchone()[0] == 0


def test_reindex_e_idempotente(isolato) -> None:
    index_all(isolato, embed=EmbedFinti())
    prima = _impronta(isolato)
    index_all(isolato, embed=EmbedFinti())
    assert _impronta(isolato) == prima


def test_errore_api_lascia_il_db_invariato(isolato) -> None:
    prima = _impronta(isolato)

    def quota_esaurita(testi: list[str]) -> list[list[float]]:
        raise RuntimeError("429 RESOURCE_EXHAUSTED")

    with pytest.raises(RuntimeError):
        index_all(isolato, embed=quota_esaurita)
    assert _impronta(isolato) == prima


# --- indice vero e API vera ---------------------------------------------------------------------


def test_every_document_indexed_with_embeddings(db) -> None:
    # sull'indice vero, senza skip: un indice rotto deve far fallire la suite
    totale, con_embedding = db.execute(
        "SELECT count(*), count(embedding) FROM documenti_chunks"
    ).fetchone()
    assert totale == con_embedding == EXPECTED_CHUNKS
    assert db.execute(SENZA_CHUNK).fetchone()[0] == 0


def test_embed_documents_api_vera() -> None:
    # il percorso batch che gli embedding finti non coprono: un vettore per testo, dimensione giusta
    if not config.GOOGLE_API_KEY:
        pytest.skip("GOOGLE_API_KEY non impostata")
    a, b = embed_documents(
        ["Canone mensile della piattaforma DevOps", "Chiusura estiva degli uffici ad agosto"]
    )
    assert len(a) == len(b) == config.EMBEDDING_DIM
    assert a != b


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


def test_l_indice_vero_non_e_stato_toccato(db, impronta_vera) -> None:
    # ultimo del modulo: i test dell'indicizzatore non hanno lasciato traccia nell'indice dell'agente
    assert _impronta(db) == impronta_vera
