"""Accesso (sync) allo schema `app`: indagini ed eventi. Connessioni autocommit col ruolo app_rw."""

from collections.abc import Callable
from datetime import datetime
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from agentic_rag import config

Row = dict[str, Any]
Conn = psycopg.Connection[Row]
STATI_ATTIVI = ["in_coda", "in_corso"]


def connect() -> Conn:
    return psycopg.connect(config.DATABASE_URL_APP, autocommit=True, row_factory=dict_row)


def run[T](fn: Callable[..., T], *args: Any) -> T:
    """Esegue `fn(conn, *args)` con una connessione a vita breve (da usare con to_thread)."""
    with connect() as conn:
        return fn(conn, *args)


def crea_indagine(conn: Conn, domanda: str, modello: str) -> UUID:
    row = conn.execute(
        "INSERT INTO app.indagini (domanda, modello) VALUES (%s, %s) RETURNING id",
        (domanda, modello),
    ).fetchone()
    assert row is not None
    return row["id"]


def segna_in_corso(conn: Conn, id: UUID) -> None:
    conn.execute(
        "UPDATE app.indagini SET stato = 'in_corso', iniziata_il = now() WHERE id = %s", (id,)
    )


def append_evento(conn: Conn, id: UUID, seq: int, tipo: str, dati: dict[str, Any]) -> None:
    conn.execute(
        "INSERT INTO app.indagini_eventi (indagine_id, seq, tipo, dati) VALUES (%s, %s, %s, %s)",
        (id, seq, tipo, Jsonb(dati)),
    )


def concludi(
    conn: Conn,
    id: UUID,
    stato: str,
    *,
    risposta: dict[str, Any] | None = None,
    errore: str | None = None,
    utilizzo: dict[str, Any] | None = None,
) -> None:
    conn.execute(
        "UPDATE app.indagini SET stato = %s, conclusa_il = now(), risposta = %s, errore = %s, "
        "utilizzo = %s WHERE id = %s",
        (
            stato,
            Jsonb(risposta) if risposta is not None else None,
            errore,
            Jsonb(utilizzo) if utilizzo is not None else None,
            id,
        ),
    )


def lista(conn: Conn, limit: int, before: datetime | None) -> list[Row]:
    return conn.execute(
        "SELECT id, domanda, stato, creata_il, conclusa_il FROM app.indagini "
        "WHERE (%(before)s::timestamptz IS NULL OR creata_il < %(before)s) "
        "ORDER BY creata_il DESC LIMIT %(limit)s",
        {"before": before, "limit": limit},
    ).fetchall()


def dettaglio(conn: Conn, id: UUID) -> Row | None:
    return conn.execute("SELECT * FROM app.indagini WHERE id = %s", (id,)).fetchone()


def stato(conn: Conn, id: UUID) -> str | None:
    row = conn.execute("SELECT stato FROM app.indagini WHERE id = %s", (id,)).fetchone()
    return row["stato"] if row else None


def eventi_dopo(conn: Conn, id: UUID, seq: int) -> list[Row]:
    return conn.execute(
        "SELECT seq, tipo, dati FROM app.indagini_eventi "
        "WHERE indagine_id = %s AND seq > %s ORDER BY seq",
        (id, seq),
    ).fetchall()


def interrompi_orfane(conn: Conn, motivo: str) -> int:
    """Marca 'interrotta' le indagini rimaste in_coda/in_corso (il processo che le eseguiva è morto)."""
    rows = conn.execute("SELECT id FROM app.indagini WHERE stato = ANY(%s)", (STATI_ATTIVI,))
    ids = [r["id"] for r in rows.fetchall()]
    for id in ids:
        row = conn.execute(
            "SELECT COALESCE(max(seq), 0) + 1 AS seq FROM app.indagini_eventi "
            "WHERE indagine_id = %s",
            (id,),
        ).fetchone()
        assert row is not None
        concludi(conn, id, "interrotta", errore=motivo)
        append_evento(conn, id, row["seq"], "interrotta", {"motivo": motivo})
    return len(ids)
