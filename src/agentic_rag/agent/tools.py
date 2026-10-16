"""Tool dell'agente: query_sql, elenca_documenti, cerca_testo, cerca_semantica, apri_documento."""

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


# Filtri comuni a `elenca_documenti` e `cerca_testo` (parametri con nome, NULL = filtro spento).
FILTRI_DOC = (
    "(%(tipo)s::text IS NULL OR d.tipo = %(tipo)s) "
    "AND (%(fornitore_id)s::text IS NULL OR d.fornitore_id = %(fornitore_id)s) "
    "AND (%(cliente_id)s::text IS NULL OR d.cliente_id = %(cliente_id)s) "
    "AND (%(data_da)s::date IS NULL OR d.data >= %(data_da)s) "
    "AND (%(data_a)s::date IS NULL OR d.data <= %(data_a)s)"
)
ELENCO_SQL = (
    "SELECT d.doc_id, d.tipo, d.data, d.titolo, d.cliente_id, d.fornitore_id, "
    "COALESCE(c.denominazione, f.denominazione) AS controparte "
    "FROM documenti d "
    "LEFT JOIN clienti c ON c.id = d.cliente_id "
    "LEFT JOIN fornitori f ON f.id = d.fornitore_id "
    f"WHERE {FILTRI_DOC} "
    "ORDER BY d.data, d.doc_id LIMIT %(limit)s OFFSET %(offset)s"
)
CONTA_SQL = f"SELECT count(*) FROM documenti d WHERE {FILTRI_DOC}"
# I frammenti (ts_headline, costoso) si calcolano solo sui k risultati, non su tutte le corrispondenze.
TESTO_SQL = (
    "WITH q AS (SELECT websearch_to_tsquery('italian', %(query)s) AS q), "
    "trovati AS ("
    "SELECT d.doc_id, d.titolo, d.tipo, d.data, d.contenuto, "
    "ts_rank_cd(d.tsv, q.q) AS rank, count(*) OVER () AS totale "
    "FROM documenti d, q "
    f"WHERE d.tsv @@ q.q AND {FILTRI_DOC} "
    "ORDER BY rank DESC, d.data, d.doc_id LIMIT %(k)s"
    ") "
    "SELECT t.doc_id, t.titolo, t.tipo, t.data, t.totale, "
    "ts_headline('italian', t.contenuto, q.q, %(opzioni)s) AS frammenti "
    "FROM trovati t, q ORDER BY t.rank DESC, t.data, t.doc_id"
)
HEADLINE_OPZIONI = (
    'MaxFragments=2, MaxWords=30, MinWords=12, FragmentDelimiter=" … ", StartSel=«, StopSel=»'
)


def _filtri(
    tipo: str | None,
    data_da: date | None,
    data_a: date | None,
    fornitore_id: str | None,
    cliente_id: str | None,
) -> dict[str, Any]:
    return {
        "tipo": tipo,
        "data_da": data_da,
        "data_a": data_a,
        "fornitore_id": fornitore_id,
        "cliente_id": cliente_id,
    }


def run_elenco(
    deps: AgentDeps,
    tipo: TipoDocumento | None,
    data_da: date | None,
    data_a: date | None,
    fornitore_id: str | None,
    cliente_id: str | None,
    pagina: int,
) -> dict[str, Any]:
    """Indice dei documenti per metadati. Non rende citabili i documenti: vanno aperti."""
    filtri = _filtri(tipo, data_da, data_a, fornitore_id, cliente_id)
    pagina = max(pagina, 1)
    per_pagina = config.ELENCO_PER_PAGINA
    totale = deps.conn.execute(CONTA_SQL, filtri).fetchone()[0]  # type: ignore[index]
    rows = deps.conn.execute(
        ELENCO_SQL, {**filtri, "limit": per_pagina, "offset": (pagina - 1) * per_pagina}
    ).fetchall()
    pagine = max((totale + per_pagina - 1) // per_pagina, 1)
    documenti = [
        {
            "doc_id": r[0],
            "tipo": r[1],
            "data": r[2].isoformat(),
            "titolo": r[3],
            "cliente_id": r[4],
            "fornitore_id": r[5],
            "controparte": r[6],
        }
        for r in rows
    ]
    deps.record(
        "elenca_documenti",
        filtri={k: (str(v) if v is not None else None) for k, v in filtri.items()},
        pagina=pagina,
        totale=totale,
        doc_ids=[d["doc_id"] for d in documenti],
    )
    out: dict[str, Any] = {
        "totale": totale,
        "pagina": pagina,
        "pagine": pagine,
        "documenti": documenti,
    }
    if not documenti:
        out["nota"] = (
            "Nessun documento con questi filtri."
            if totale == 0
            else f"Pagina oltre l'ultima: le pagine sono {pagine}."
        )
    return out


def elenca_documenti(
    ctx: RunContext[AgentDeps],
    tipo: TipoDocumento | None = None,
    data_da: date | None = None,
    data_a: date | None = None,
    fornitore_id: str | None = None,
    cliente_id: str | None = None,
    pagina: int = 1,
) -> dict[str, Any]:
    """Elenca i documenti per metadati (tipo, periodo, fornitore FOR-*, cliente CLI-*), senza testo.

    Utile quando conosci già la controparte o il periodo: mostra tutti i documenti che esistono,
    in ordine di data, 30 per pagina (`totale` e `pagine` dicono quanti sono). Restituisce solo
    titoli: per leggere e citare un documento aprilo con apri_documento.
    """
    return run_elenco(ctx.deps, tipo, data_da, data_a, fornitore_id, cliente_id, pagina)


def run_testo(
    deps: AgentDeps,
    query: str,
    k: int,
    tipo: TipoDocumento | None,
    data_da: date | None,
    data_a: date | None,
    fornitore_id: str | None,
    cliente_id: str | None,
) -> dict[str, Any]:
    termini = deps.conn.execute(
        "SELECT numnode(websearch_to_tsquery('italian', %s))", (query,)
    ).fetchone()[0]  # type: ignore[index]
    if not termini:
        raise ModelRetry(
            "La ricerca non contiene termini utili (solo parole vuote o simboli): "
            "usa parole significative, unite da `or` se sono alternative."
        )
    filtri = _filtri(tipo, data_da, data_a, fornitore_id, cliente_id)
    rows = deps.conn.execute(
        TESTO_SQL,
        {
            **filtri,
            "query": query,
            "k": min(max(k, 1), config.TESTO_MAX_K),
            "opzioni": HEADLINE_OPZIONI,
        },
    ).fetchall()
    totale = rows[0][4] if rows else 0
    risultati = [
        {
            "doc_id": r[0],
            "titolo": r[1],
            "tipo": r[2],
            "data": r[3].isoformat(),
            "frammenti": r[5],
        }
        for r in rows
    ]
    deps.seen_ids |= {r["doc_id"] for r in risultati}
    deps.record(
        "cerca_testo",
        query=query,
        totale=totale,
        doc_ids=[r["doc_id"] for r in risultati],
    )
    if not risultati:
        return {
            "totale": 0,
            "risultati": [],
            "nota": (
                "Nessun documento contiene questi termini. Prima di concludere che non è "
                "documentato, prova sinonimi uniti da `or` o togli qualche filtro."
            ),
        }
    return {"totale": totale, "risultati": risultati}


def cerca_testo(
    ctx: RunContext[AgentDeps],
    query: str,
    k: int = 5,
    tipo: TipoDocumento | None = None,
    data_da: date | None = None,
    data_a: date | None = None,
    fornitore_id: str | None = None,
    cliente_id: str | None = None,
) -> dict[str, Any]:
    """Cerca parole nel titolo e nel testo dei documenti (italiano, riconosce le forme flesse).

    Un documento è restituito solo se contiene i termini. Sintassi: le parole separate da spazio
    devono esserci tutte; `or` tra alternative (es. `trasferta or viaggio or treno`); "frase
    esatta" tra virgolette; `-parola` per escludere. Adatta a nomi, controparti, oggetti precisi.
    `totale` = documenti con corrispondenza; i frammenti mostrano i termini «evidenziati».
    """
    return run_testo(ctx.deps, query, k, tipo, data_da, data_a, fornitore_id, cliente_id)


def run_semantica(
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
        "cerca_semantica",
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


def cerca_semantica(
    ctx: RunContext[AgentDeps],
    query: str,
    k: int = 5,
    tipo: TipoDocumento | None = None,
    data_da: date | None = None,
    data_a: date | None = None,
    fornitore_id: str | None = None,
    cliente_id: str | None = None,
) -> dict[str, Any]:
    """Ricerca per significato nei documenti (contratti, email, lettere, verbali).

    Trova passaggi che esprimono un concetto anche con parole diverse da quelle della query:
    descrivi in una frase il fatto che cerchi. Meno adatta a nomi, codici e importi esatti.
    Restituisce solo passaggi pertinenti; se non c'è nulla lo dichiara. Usa i filtri (periodo,
    fornitore FOR-*, cliente CLI-*, tipo) per restringere. Distanza più bassa = più pertinente.
    """
    return run_semantica(ctx.deps, query, k, tipo, data_da, data_a, fornitore_id, cliente_id)


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
