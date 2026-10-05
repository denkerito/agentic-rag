"""Indicizzazione RAG: chunking dei documenti, embedding, riscrittura di documenti_chunks.

Uso: python -m agentic_rag.rag.indexer
"""

import collections
from dataclasses import dataclass

import psycopg
from pgvector import Vector
from pgvector.psycopg import register_vector

from agentic_rag import config
from agentic_rag.rag.chunking import Documento, chunk_documento, testo_per_embedding
from agentic_rag.rag.embeddings import embed_documents

DOCS_SQL = """
SELECT d.doc_id, d.tipo, d.data::text, d.titolo, d.contenuto,
       CASE WHEN f.id IS NOT NULL THEN 'Fornitore: ' || f.denominazione
            WHEN c.id IS NOT NULL THEN 'Cliente: ' || c.denominazione END
FROM documenti d
LEFT JOIN fornitori f ON f.id = d.fornitore_id
LEFT JOIN clienti c ON c.id = d.cliente_id
ORDER BY d.doc_id
"""


@dataclass(frozen=True)
class ChunkRecord:
    doc_id: str
    tipo: str
    chunk_index: int
    testo: str
    testo_embedding: str


def build_chunks(docs: list[Documento]) -> list[ChunkRecord]:
    return [
        ChunkRecord(d.doc_id, d.tipo, i, testo, testo_per_embedding(d, testo))
        for d in docs
        for i, testo in enumerate(chunk_documento(d.tipo, d.contenuto))
    ]


def load_documents(conn: psycopg.Connection) -> list[Documento]:
    rows = conn.execute(DOCS_SQL).fetchall()
    return [Documento(r[0], r[1], r[2], r[3], r[4], r[5]) for r in rows]


def index_all(conn: psycopg.Connection) -> list[ChunkRecord]:
    chunks = build_chunks(load_documents(conn))
    # Tutti gli embedding prima di scrivere: se l'API fallisce il DB resta invariato.
    vectors = embed_documents([c.testo_embedding for c in chunks])
    register_vector(conn)
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM documenti_chunks")
        cur.executemany(
            "INSERT INTO documenti_chunks (doc_id, chunk_index, testo, embedding) "
            "VALUES (%s, %s, %s, %s)",
            [(c.doc_id, c.chunk_index, c.testo, Vector(v)) for c, v in zip(chunks, vectors)],
        )
    return chunks


def main() -> None:
    if not config.DATABASE_URL:
        raise SystemExit("DATABASE_URL non impostata (vedi .env.example)")
    with psycopg.connect(config.DATABASE_URL) as conn:
        chunks = index_all(conn)
    per_tipo = collections.Counter(c.tipo for c in chunks)
    print(f"modello {config.EMBEDDING_MODEL}, dimensione {config.EMBEDDING_DIM}")
    print(f"documenti {len({c.doc_id for c in chunks})}, chunk {len(chunks)}")
    for tipo, n in sorted(per_tipo.items()):
        print(f"  {tipo:14} {n:>4}")


if __name__ == "__main__":
    main()
