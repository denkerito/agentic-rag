"""Validatore applicativo delle query dell'agente.

Seconda linea di difesa: la barriera reale è il ruolo `agent_ro` (sola lettura, timeout).
Qui si danno al modello errori chiari prima di arrivare al database.
"""

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

FORBIDDEN_FUNCTION_PREFIXES = ("pg_", "lo_", "dblink", "query_to_xml", "xpath")
FORBIDDEN_FUNCTIONS = {"set_config", "current_setting", "txid_current", "version"}
FORBIDDEN_NODES = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Create,
    exp.Drop,
    exp.Alter,
    exp.Command,
    exp.Copy,
    exp.Into,
    exp.Lock,
    exp.Set,
    exp.Merge,
)


class SqlRejected(ValueError):
    """Query non ammessa; il messaggio è destinato al modello."""


def _function_names(tree: exp.Expression) -> set[str]:
    names = {f.name.lower() for f in tree.find_all(exp.Func) if f.name}
    names |= {a.name.lower() for a in tree.find_all(exp.Anonymous)}
    return names


def validate_select(sql: str, allowed_relations: set[str]) -> str:
    """Restituisce la query normalizzata o solleva SqlRejected."""
    if not sql.strip():
        raise SqlRejected("Query vuota.")
    try:
        statements = [s for s in sqlglot.parse(sql, dialect="postgres") if s is not None]
    except SqlglotError as e:
        raise SqlRejected(f"SQL non valido: {str(e).splitlines()[0]}") from e
    if len(statements) != 1:
        raise SqlRejected("Ammessa una sola istruzione SELECT per chiamata.")
    tree = statements[0]
    if not isinstance(tree, (exp.Select, exp.Union, exp.Subquery)):
        raise SqlRejected("Sono ammesse solo query SELECT (anche con WITH/UNION).")
    if tree.find(*FORBIDDEN_NODES):
        raise SqlRejected("La query contiene operazioni di scrittura o non ammesse.")

    for name in _function_names(tree):
        if name in FORBIDDEN_FUNCTIONS or name.startswith(FORBIDDEN_FUNCTION_PREFIXES):
            raise SqlRejected(f"Funzione non ammessa: {name}.")

    ctes = {c.alias.lower() for c in tree.find_all(exp.CTE)}
    for table in tree.find_all(exp.Table):
        if table.args.get("db") or table.args.get("catalog"):
            raise SqlRejected("Non sono ammessi riferimenti a schemi: usa i nomi delle tabelle.")
        name = table.name.lower()
        if name not in ctes and name not in allowed_relations:
            raise SqlRejected(
                f"Relazione non ammessa: {table.name}. "
                f"Disponibili: {', '.join(sorted(allowed_relations))}."
            )
    return tree.sql(dialect="postgres")
