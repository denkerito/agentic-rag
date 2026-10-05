"""Ricerca semantica sui chunk dei documenti (base del futuro tool `cerca_documenti`)."""

from dataclasses import dataclass

import psycopg
from pgvector import Vector
from pgvector.psycopg import register_vector

from agentic_rag.rag.embeddings import embed_query


@dataclass(frozen=True)
class ChunkHit:
    doc_id: str
    chunk_index: int
    titolo: str
    tipo: str
    testo: str
    distanza: float


def search_chunks(
    conn: psycopg.Connection,
    query: str,
    k: int = 5,
    *,
    tipo: str | None = None,
    fornitore_id: str | None = None,
    cliente_id: str | None = None,
) -> list[ChunkHit]:
    register_vector(conn)
    vec = Vector(embed_query(query))
    sql = (
        "SELECT c.doc_id, c.chunk_index, d.titolo, d.tipo, c.testo, c.embedding <=> %s AS dist "
        "FROM documenti_chunks c JOIN documenti d USING (doc_id) "
        "WHERE c.embedding IS NOT NULL "
        "AND (%s::text IS NULL OR d.tipo = %s) "
        "AND (%s::text IS NULL OR d.fornitore_id = %s) "
        "AND (%s::text IS NULL OR d.cliente_id = %s) "
        "ORDER BY dist LIMIT %s"
    )
    params = (vec, tipo, tipo, fornitore_id, fornitore_id, cliente_id, cliente_id, k)
    return [ChunkHit(*row) for row in conn.execute(sql, params).fetchall()]
