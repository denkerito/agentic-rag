"""DDL con commenti generato dal database, per il system prompt."""

import psycopg

COLUMNS_SQL = """
SELECT c.relname, c.relkind, a.attname, format_type(a.atttypid, a.atttypmod),
       obj_description(c.oid, 'pg_class'), col_description(c.oid, a.attnum)
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace AND n.nspname = 'public'
JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
WHERE c.relkind IN ('r', 'v') AND c.relname <> 'documenti_chunks'
ORDER BY c.relkind, c.relname, a.attnum
"""


def build_schema_ddl(conn: psycopg.Connection) -> str:
    tables: dict[str, list[str]] = {}
    heads: dict[str, str] = {}
    for rel, kind, col, typ, rel_comment, col_comment in conn.execute(COLUMNS_SQL).fetchall():
        if rel not in tables:
            label = "VISTA" if kind == "v" else "TABELLA"
            heads[rel] = f"-- {label} {rel}" + (f": {rel_comment}" if rel_comment else "")
            tables[rel] = []
        tables[rel].append(f"  {col} {typ}" + (f"  -- {col_comment}" if col_comment else ""))
    return "\n\n".join(
        f"{heads[r]}\n{r}(\n" + ",\n".join(cols) + "\n)" for r, cols in tables.items()
    )
