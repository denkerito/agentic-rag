"""Metriche sulle fonti: ID citati e tabelle effettivamente lette dall'agente."""

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

from agentic_rag.agent.output import Risposta
from agentic_rag.eval.groundtruth import Domanda

_BASE_ECONOMICO = frozenset(
    {"scritture_contabili", "piano_dei_conti", "fatture", "clienti", "fornitori"}
)
# Tabelle base delle viste (schema.sql). Un test d'integrazione le confronta con il database.
VISTE: dict[str, frozenset[str]] = {
    "v_economico": _BASE_ECONOMICO,
    "v_economico_mensile": _BASE_ECONOMICO,
    "v_margine_mensile": _BASE_ECONOMICO,
}
# I tool sui documenti leggono queste tabelle senza passare da una SQL.
TABELLE_PER_TOOL: dict[str, frozenset[str]] = {
    "cerca_documenti": frozenset({"documenti", "documenti_chunks"}),
    "apri_documento": frozenset({"documenti"}),
}


def tabelle_in_sql(sql: str) -> set[str]:
    """Tabelle (CTE escluse, viste incluse) nominate da una query."""
    try:
        alberi = [t for t in sqlglot.parse(sql, dialect="postgres") if t is not None]
    except SqlglotError:
        return set()
    out: set[str] = set()
    for tree in alberi:
        ctes = {c.alias.lower() for c in tree.find_all(exp.CTE)}
        for t in tree.find_all(exp.Table):
            nome = t.name.lower()
            if nome and nome not in ctes:
                out.add(nome)
    return out


def tabelle_lette(trace: Iterable[dict[str, Any]]) -> set[str]:
    """Tabelle lette dall'agente: dalle SQL (viste espanse) e dai tool sui documenti."""
    out: set[str] = set()
    for ev in trace:
        kind = ev.get("kind")
        if kind == "sql":
            for nome in tabelle_in_sql(str(ev.get("sql", ""))):
                out.add(nome)
                out |= VISTE.get(nome, frozenset())
        else:
            out |= TABELLE_PER_TOOL.get(str(kind), frozenset())
    return out


def sql_dell_agente(trace: Iterable[dict[str, Any]]) -> list[str]:
    return [str(ev["sql"]) for ev in trace if ev.get("kind") == "sql"]


def id_citati(risposta: Risposta) -> set[str]:
    return set(risposta.fonti) | {f for n in risposta.numeri for f in n.fonti}


@dataclass
class MetricheFonti:
    id_attesi: int
    id_trovati: int
    id_extra: int  # citati e non attesi: non penalizzati, solo contati
    tabelle_attese: int
    tabelle_trovate: int
    # citate ma mai ricevute dai tool: deve essere 0 (lo garantisce il validator)
    citate_non_viste: int
    # riservato al report privato
    id_mancanti: list[str] = field(default_factory=list)
    tabelle_mancanti: list[str] = field(default_factory=list)

    @property
    def id_recall(self) -> float | None:
        return self.id_trovati / self.id_attesi if self.id_attesi else None

    @property
    def tabelle_recall(self) -> float | None:
        return self.tabelle_trovate / self.tabelle_attese if self.tabelle_attese else None


def valuta_fonti(
    domanda: Domanda,
    risposta: Risposta,
    trace: list[dict[str, Any]],
    seen_ids: set[str],
) -> MetricheFonti:
    citati = id_citati(risposta)
    attesi = set(domanda.id_attesi)
    letti = tabelle_lette(trace)
    tabelle_attese = set(domanda.tabelle_attese)
    return MetricheFonti(
        id_attesi=len(attesi),
        id_trovati=len(attesi & citati),
        id_extra=len(citati - attesi),
        tabelle_attese=len(tabelle_attese),
        tabelle_trovate=len(tabelle_attese & letti),
        citate_non_viste=len(citati - seen_ids),
        id_mancanti=sorted(attesi - citati),
        tabelle_mancanti=sorted(tabelle_attese - letti),
    )
