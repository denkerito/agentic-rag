"""Tool dell'agente: query_sql, cerca_documenti, apri_documento."""

from datetime import date
from decimal import Decimal
from typing import Any, Literal

import psycopg
from pydantic_ai import ModelRetry, RunContext

from agentic_rag.agent import config
from agentic_rag.agent.deps import AgentDeps
from agentic_rag.agent.ids import extract_ids
from agentic_rag.agent.sql_guard import SqlRejected, validate_select
from agentic_rag.rag.search import search_chunks

TipoDocumento = Literal[
    "email", "contratto", "lettera", "verbale", "preventivo", "addendum", "nota_interna"
]


def _cell(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return [_cell(v) for v in value]
    if value is None or isinstance(value, (int, float, bool)):
        return value
    text = str(value)
    if len(text) <= config.SQL_MAX_CELL_CHARS:
        return text
    return text[: config.SQL_MAX_CELL_CHARS] + "…"


def run_query(deps: AgentDeps, sql: str) -> dict[str, Any]:
    """Esegue una SELECT validata in una transazione di sola lettura."""
    try:
        query = validate_select(sql, deps.relations)
    except SqlRejected as e:
        raise ModelRetry(str(e)) from e
    try:
        with deps.conn.transaction(), deps.conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute(query)  # type: ignore[arg-type]
            columns = [d.name for d in cur.description or []]
            rows = cur.fetchmany(config.SQL_MAX_ROWS + 1)
    except psycopg.Error as e:
        raise ModelRetry(f"Errore SQL: {str(e).splitlines()[0]}") from e
    truncated = len(rows) > config.SQL_MAX_ROWS
    out = [[_cell(v) for v in r] for r in rows[: config.SQL_MAX_ROWS]]
    deps.seen_ids |= extract_ids(str(out))
    deps.record("sql", sql=query, n_righe=len(out), troncato=truncated)
    return {"colonne": columns, "righe": out, "n_righe": len(out), "troncato": truncated}


def query_sql(ctx: RunContext[AgentDeps], sql: str) -> dict[str, Any]:
    """Esegue una query SELECT (PostgreSQL, sola lettura) e restituisce colonne e righe.

    Usa le viste v_* per ricavi/costi/margine. Per ogni aggregazione includi gli ID delle
    fonti (colonna `fonti` delle viste, oppure array_agg(id)). Mai calcolare a mente:
    differenze e percentuali vanno calcolate nella query.
    """
    return run_query(ctx.deps, sql)


def run_search(
    deps: AgentDeps,
    query: str,
    k: int,
    tipo: TipoDocumento | None,
    data_da: date | None,
    data_a: date | None,
    fornitore_id: str | None,
    cliente_id: str | None,
) -> dict[str, Any]:
    hits = search_chunks(
        deps.conn,
        query,
        min(max(k, 1), config.SEARCH_MAX_K),
        tipo=tipo,
        fornitore_id=fornitore_id,
        cliente_id=cliente_id,
        data_da=data_da,
        data_a=data_a,
    )
    relevant = [h for h in hits if h.distanza <= config.SEARCH_MAX_DISTANCE]
    deps.seen_ids |= {h.doc_id for h in relevant}
    deps.record(
        "cerca_documenti",
        query=query,
        n_trovati=len(hits),
        n_pertinenti=len(relevant),
        doc_ids=[h.doc_id for h in relevant],
    )
    if not relevant:
        return {"risultati": [], "nota": "Nessun documento pertinente: non inventare una causa."}
    return {
        "risultati": [
            {
                "doc_id": h.doc_id,
                "titolo": h.titolo,
                "tipo": h.tipo,
                "data": h.data.isoformat(),
                "distanza": round(h.distanza, 3),
                "testo": h.testo,
            }
            for h in relevant
        ]
    }


def cerca_documenti(
    ctx: RunContext[AgentDeps],
    query: str,
    k: int = 5,
    tipo: TipoDocumento | None = None,
    data_da: date | None = None,
    data_a: date | None = None,
    fornitore_id: str | None = None,
    cliente_id: str | None = None,
) -> dict[str, Any]:
    """Ricerca semantica nei documenti (contratti, email, lettere, verbali).

    Restituisce solo chunk pertinenti; se non c'è nulla lo dichiara. Usa i filtri (periodo,
    fornitore FOR-*, cliente CLI-*, tipo) per restringere. Distanza più bassa = più pertinente.
    """
    return run_search(ctx.deps, query, k, tipo, data_da, data_a, fornitore_id, cliente_id)


def run_open(deps: AgentDeps, doc_id: str, offset: int) -> dict[str, Any]:
    row = deps.conn.execute(
        "SELECT doc_id, tipo, data, titolo, fornitore_id, cliente_id, contenuto "
        "FROM documenti WHERE doc_id = %s",
        (doc_id,),
    ).fetchone()
    if row is None:
        raise ModelRetry(f"Documento {doc_id} inesistente: usa un doc_id restituito dai tool.")
    contenuto = row[6]
    offset = max(offset, 0)
    parte = contenuto[offset : offset + config.DOC_MAX_CHARS]
    truncated = offset + len(parte) < len(contenuto)
    deps.seen_ids.add(row[0])
    deps.record("apri_documento", doc_id=doc_id, offset=offset, troncato=truncated)
    return {
        "doc_id": row[0],
        "tipo": row[1],
        "data": row[2].isoformat(),
        "titolo": row[3],
        "fornitore_id": row[4],
        "cliente_id": row[5],
        "totale_caratteri": len(contenuto),
        "offset": offset,
        "troncato": truncated,
        "contenuto": parte,
    }


def apri_documento(ctx: RunContext[AgentDeps], doc_id: str, offset: int = 0) -> dict[str, Any]:
    """Apre un documento per ID (es. CTR-001, DOC-EML-003). Se troncato, usa offset maggiore."""
    return run_open(ctx.deps, doc_id, offset)
