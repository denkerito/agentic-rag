"""Metriche sui numeri: valori attesi (da `query_sql`) contro quelli dichiarati dall'agente."""

import csv
import re
import sqlite3
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from agentic_rag import config
from agentic_rag.agent.output import Risposta

MAX_RIGHE_ATTESE = 500
MAX_VALORI_ATTESI = 25  # oltre, la query restituisce un elenco, non "i numeri della risposta"
TOLLERANZA = Decimal("0.01")

# 1.234,56 | 1,234.56 | 1 234,56 | 12,5 | 41200.00 | 1.234 (ambiguo)
_NUMERO = re.compile(r"(?<![\w.])-?\d{1,3}(?:[.\s]\d{3})+(?:,\d+)?|(?<![\w.])-?\d+(?:[.,]\d+)?")
_NUMERO_EN = re.compile(r"(?<![\w.])-?\d{1,3}(?:,\d{3})+(?:\.\d+)?")


def _dec(testo: str) -> Decimal | None:
    try:
        return Decimal(testo)
    except InvalidOperation:
        return None


def estrai_numeri(testo: str) -> set[Decimal]:
    """Tutti i numeri plausibili in un testo (formato italiano e inglese, `€`, `%`).

    I token ambigui (es. "1.234") producono entrambe le letture: la corrispondenza con un valore
    atteso avviene se una qualunque lettura coincide.
    """
    out: set[Decimal] = set()
    for m in _NUMERO_EN.finditer(testo):
        d = _dec(m.group(0).replace(",", ""))
        if d is not None:
            out.add(d)
    for m in _NUMERO.finditer(testo):
        tok = m.group(0)
        compatto = re.sub(r"\s", "", tok)
        if "," in compatto and "." in compatto:
            # il separatore più a destra è quello decimale
            if compatto.rfind(",") > compatto.rfind("."):
                letture = [compatto.replace(".", "").replace(",", ".")]
            else:
                letture = [compatto.replace(",", "")]
        elif "," in compatto:
            letture = [compatto.replace(",", ".")]
        elif "." in compatto:
            letture = [compatto.replace(".", ""), compatto]  # 1.234 → migliaia oppure decimale
        else:
            letture = [compatto]
        for lettura in letture:
            d = _dec(lettura)
            if d is not None:
                out.add(d)
    return out


def corrisponde(atteso: Decimal, trovato: Decimal) -> bool:
    """Uguale entro 0,01, oppure uguale all'atteso arrotondato come l'ha scritto l'agente."""
    if abs(atteso - trovato) <= TOLLERANZA:
        return True
    decimali = max(0, -trovato.as_tuple().exponent)  # type: ignore[operator]
    return atteso.quantize(Decimal(1).scaleb(-decimali), rounding=ROUND_HALF_UP) == trovato


@dataclass
class RisultatoQuery:
    valori: set[Decimal] = field(default_factory=set)
    n_righe: int = 0
    errore: str | None = None  # solo il nome dell'eccezione: mai testo che possa contenere dati


CSV_DIR: Path = config.DATA_DIR / "csv"
_NUM = re.compile(r"-?\d+(\.\d+)?")


def _colonna_numerica(valori: list[str]) -> bool:
    pieni = [v for v in valori if v != ""]
    # niente zeri iniziali: sono codici (P.IVA, ID), non importi
    return bool(pieni) and all(_NUM.fullmatch(v) and not re.match(r"-?0\d", v) for v in pieni)


def carica_csv_in_sqlite(csv_dir: Path) -> sqlite3.Connection:
    """SQLite in memoria con una tabella per ogni CSV, con le colonne del CSV.

    Le `query_sql` attese sono scritte per questo layout (colonne dei CSV, `strftime` di SQLite),
    non per lo schema normalizzato di Postgres.
    """
    conn = sqlite3.connect(":memory:")
    for path in sorted(csv_dir.glob("*.csv")):
        with path.open(encoding="utf-8", newline="") as f:
            righe = list(csv.reader(f))
        if not righe:
            continue
        intestazione, dati = righe[0], righe[1:]
        convertitori = []
        for i in range(len(intestazione)):
            valori = [r[i] for r in dati if i < len(r)]
            if _colonna_numerica(valori):
                intero = all("." not in v for v in valori)
                convertitori.append(int if intero else float)
            else:
                convertitori.append(str)
        colonne = ", ".join('"' + h.replace('"', '""') + '"' for h in intestazione)
        conn.execute(f'CREATE TABLE "{path.stem}" ({colonne})')
        segnaposto = ", ".join("?" * len(intestazione))
        conn.executemany(
            f'INSERT INTO "{path.stem}" VALUES ({segnaposto})',
            [
                [
                    (conv(r[i]) if i < len(r) and r[i] != "" else None)
                    for i, conv in enumerate(convertitori)
                ]
                for r in dati
            ],
        )
    conn.execute("PRAGMA query_only = ON")
    return conn


def _celle_numeriche(righe: list[tuple[Any, ...]]) -> set[Decimal]:
    out: set[Decimal] = set()
    for riga in righe:
        for v in riga:
            if isinstance(v, bool) or v is None:
                continue
            if isinstance(v, (int, float, Decimal)):
                d = _dec(str(v))
                if d is not None:
                    out.add(d)
    return out


def esegui_query_attesa(sql: str | None, csv_dir: Path | None = None) -> RisultatoQuery | None:
    """Esegue la query attesa sui CSV (SQLite in memoria, sola lettura). None se non c'è."""
    if not sql:
        return None
    try:
        conn = carica_csv_in_sqlite(csv_dir or CSV_DIR)
        try:
            righe = conn.execute(sql).fetchmany(MAX_RIGHE_ATTESE)
        finally:
            conn.close()
    except (sqlite3.Error, OSError, ValueError) as e:
        return RisultatoQuery(errore=type(e).__name__)
    return RisultatoQuery(valori=_celle_numeriche(righe), n_righe=len(righe))


@dataclass
class MetricheNumeri:
    attesi: int
    trovati: int
    motivo_na: str | None = None  # perché il controllo non si applica
    # riservato al report privato
    attesi_valori: list[str] = field(default_factory=list)
    mancanti: list[str] = field(default_factory=list)

    @property
    def applicabile(self) -> bool:
        return self.motivo_na is None

    @property
    def recall(self) -> float | None:
        return self.trovati / self.attesi if self.applicabile and self.attesi else None


def numeri_dichiarati(risposta: Risposta) -> set[Decimal]:
    """Numeri dell'agente: `numeri[].valore` e quelli scritti nella conclusione."""
    out = estrai_numeri(risposta.conclusione)
    for n in risposta.numeri:
        out |= estrai_numeri(n.valore)
    return out


def valuta_numeri(atteso: RisultatoQuery | None, risposta: Risposta) -> MetricheNumeri:
    if atteso is None:
        return MetricheNumeri(0, 0, motivo_na="nessuna query attesa")
    if atteso.errore:
        return MetricheNumeri(0, 0, motivo_na=f"query attesa non eseguibile ({atteso.errore})")
    if not atteso.valori:
        return MetricheNumeri(0, 0, motivo_na="la query attesa non restituisce numeri")
    if len(atteso.valori) > MAX_VALORI_ATTESI:
        return MetricheNumeri(0, 0, motivo_na=f"più di {MAX_VALORI_ATTESI} valori attesi")
    dichiarati = numeri_dichiarati(risposta)
    trovati = [a for a in atteso.valori if any(corrisponde(a, d) for d in dichiarati)]
    mancanti = sorted(atteso.valori - set(trovati))
    return MetricheNumeri(
        attesi=len(atteso.valori),
        trovati=len(trovati),
        attesi_valori=[str(v) for v in sorted(atteso.valori)],
        mancanti=[str(v) for v in mancanti],
    )
