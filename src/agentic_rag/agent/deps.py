from dataclasses import dataclass, field
from typing import Any

import psycopg

DOCUMENTI_SOLO_TOOL = frozenset({"documenti", "documenti_chunks"})


@dataclass
class AgentDeps:
    conn: psycopg.Connection  # connessione con il ruolo agent_ro
    relations: set[str]  # tabelle e viste interrogabili
    seen_ids: set[str] = field(default_factory=set)
    trace: list[dict[str, Any]] = field(default_factory=list)

    def record(self, kind: str, **data: Any) -> None:
        self.trace.append({"kind": kind, **data})


def list_relations(conn: psycopg.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
    ).fetchall()
    # i documenti si leggono solo con i tool dedicati (elenco, ricerche, apertura): ogni accesso
    # resta tracciato e il testo non finisce in blocco nel contesto
    return {r[0] for r in rows} - DOCUMENTI_SOLO_TOOL
