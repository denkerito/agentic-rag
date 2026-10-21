"""Controllo dell'ambiente prima della batteria: meglio un messaggio chiaro che minuti di attesa."""

from collections.abc import Sequence

import psycopg

from agentic_rag import config
from agentic_rag.agent.model import OPENROUTER_PREFIX

CONNECT_TIMEOUT_S = 5
COLONNA_FULLTEXT_SQL = (
    "SELECT 1 FROM information_schema.columns "
    "WHERE table_schema = 'public' AND table_name = 'documenti' AND column_name = 'tsv'"
)


def controlla_schema(conn: psycopg.Connection) -> list[str]:
    """Problemi dello schema visto dall'agente. Senza la colonna full-text `cerca_testo` fallisce
    a metà indagine, e nell'eval l'errore passerebbe per un problema dell'agente."""
    if conn.execute(COLONNA_FULLTEXT_SQL).fetchone() is None:
        return [
            (
                "ricerca testuale non inizializzata (manca documenti.tsv): esegui "
                "`python -m agentic_rag.db.init --fulltext-only`"
            )
        ]
    return []


def controlla_ambiente(
    modelli: Sequence[str] = (),
    db_url: str | None = None,
    google_key: str | None = None,
    openrouter_key: str | None = None,
) -> list[str]:
    """Elenco dei problemi che impedirebbero la batteria (vuoto se tutto ok).

    `modelli`: agente e giudice in uso; la chiave OpenRouter serve solo se uno è `openrouter:`.
    """
    db_url = config.DATABASE_URL_AGENT if db_url is None else db_url
    google_key = config.GOOGLE_API_KEY if google_key is None else google_key
    openrouter_key = config.OPENROUTER_API_KEY if openrouter_key is None else openrouter_key
    problemi: list[str] = []
    if not db_url:
        problemi.append("DATABASE_URL_AGENT non impostata nel .env")
    else:
        try:
            conn = psycopg.connect(db_url, connect_timeout=CONNECT_TIMEOUT_S)
        except psycopg.Error:
            problemi.append(
                "il database non risponde: avvialo con `docker compose up -d db` "
                "(e controlla DATABASE_URL_AGENT nel .env)"
            )
        else:
            try:
                problemi += controlla_schema(conn)
            finally:
                conn.close()
    if not google_key:
        problemi.append(
            "GOOGLE_API_KEY non impostata nel .env (serve agli embedding della ricerca semantica)"
        )
    su_openrouter = sorted({m for m in modelli if m.startswith(OPENROUTER_PREFIX)})
    if su_openrouter and not openrouter_key:
        problemi.append(
            f"OPENROUTER_API_KEY non impostata nel .env (serve a {', '.join(su_openrouter)})"
        )
    return problemi
