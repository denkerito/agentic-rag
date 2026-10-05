"""Inizializzazione del database: ruoli, schema, grant, caricamento dati.

Uso: python -m agentic_rag.db.init [--reset]
"""

import argparse
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

from agentic_rag import config
from agentic_rag.db.load import load_all

OWNER_ROLE = "agentic_owner"
AGENT_ROLE = "agent_ro"
SCHEMA_FILE = Path(__file__).with_name("schema.sql")


def _creds(url: str) -> tuple[str, str, str]:
    info = conninfo_to_dict(url)
    return info["user"], info.get("password", ""), info["dbname"]


def _upsert_role(cur: psycopg.Cursor, role: str, password: str) -> None:
    cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,))
    verb = "ALTER" if cur.fetchone() else "CREATE"
    cur.execute(
        sql.SQL("{} ROLE {} LOGIN PASSWORD {}").format(
            sql.SQL(verb), sql.Identifier(role), sql.Literal(password)
        )
    )


def bootstrap(admin_url: str, owner_url: str, agent_url: str) -> None:
    """Come superuser: ruoli, proprietà del database, estensione, restrizioni di agent_ro."""
    owner, owner_pw, db = _creds(owner_url)
    agent, agent_pw, agent_db = _creds(agent_url)
    if owner != OWNER_ROLE or agent != AGENT_ROLE or agent_db != db:
        raise SystemExit(
            f"Le URL devono usare i ruoli {OWNER_ROLE}/{AGENT_ROLE} e lo stesso database"
        )
    dbname, role_o, role_a = sql.Identifier(db), sql.Identifier(owner), sql.Identifier(agent)
    with psycopg.connect(admin_url, autocommit=True) as conn, conn.cursor() as cur:
        _upsert_role(cur, owner, owner_pw)
        _upsert_role(cur, agent, agent_pw)
        cur.execute(sql.SQL("ALTER DATABASE {} OWNER TO {}").format(dbname, role_o))
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        cur.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(dbname))
        cur.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(dbname, role_a))
        cur.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
        cur.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(role_a))
        cur.execute(
            sql.SQL(
                "ALTER ROLE {} SET default_transaction_read_only = on; "
                "ALTER ROLE {} SET statement_timeout = '10s'; "
                "ALTER ROLE {} SET idle_in_transaction_session_timeout = '30s'"
            ).format(role_a, role_a, role_a)
        )


def apply_schema(owner_url: str, reset: bool) -> None:
    ddl = SCHEMA_FILE.read_text(encoding="utf-8").replace(
        "{EMBEDDING_DIM}", str(config.EMBEDDING_DIM)
    )
    with psycopg.connect(owner_url, autocommit=True) as conn, conn.cursor() as cur:
        if reset:
            cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
            for (table,) in cur.fetchall():
                cur.execute(
                    sql.SQL("DROP TABLE IF EXISTS {} CASCADE").format(sql.Identifier(table))
                )
        cur.execute(ddl)
        role_a = sql.Identifier(AGENT_ROLE)
        cur.execute(sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA public TO {}").format(role_a))
        cur.execute(
            sql.SQL(
                "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public GRANT SELECT ON TABLES TO {}"
            ).format(sql.Identifier(OWNER_ROLE), role_a)
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Inizializza il database di agentic-rag")
    parser.add_argument("--reset", action="store_true", help="elimina le tabelle esistenti")
    args = parser.parse_args()
    for name in ("DATABASE_URL_ADMIN", "DATABASE_URL", "DATABASE_URL_AGENT"):
        if not getattr(config, name):
            raise SystemExit(f"{name} non impostata (vedi .env.example)")

    bootstrap(config.DATABASE_URL_ADMIN, config.DATABASE_URL, config.DATABASE_URL_AGENT)
    apply_schema(config.DATABASE_URL, args.reset)
    with psycopg.connect(config.DATABASE_URL) as conn:
        counts = load_all(conn)
    for table, n in counts.items():
        print(f"{table:22} {n:>6}")


if __name__ == "__main__":
    main()
