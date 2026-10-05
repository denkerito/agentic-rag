"""Caricamento di data/csv e data/documenti nel database.

Legge solo da DATA_DIR: non accede mai a eval/ground_truth/.
"""

import csv
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path

import psycopg

from agentic_rag.config import DATA_DIR, ROOT_DIR

Row = dict[str, str]


def read_csv(path: Path) -> list[Row]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def to_none(value: str) -> str | None:
    return value if value != "" else None


def to_pct(value: str) -> Decimal:
    return Decimal(value.strip().rstrip("%"))


def to_bool(value: str) -> bool:
    return value.strip().lower() == "true"


def split_controparte(controparte_id: str) -> tuple[str | None, str | None]:
    """Restituisce (cliente_id, fornitore_id) dal prefisso dell'ID."""
    if controparte_id.startswith("CLI-"):
        return controparte_id, None
    if controparte_id.startswith("FOR-"):
        return None, controparte_id
    if controparte_id == "":
        return None, None
    raise ValueError(f"controparte_id sconosciuto: {controparte_id!r}")


def split_riferimento(
    riferimento_id: str,
) -> tuple[str | None, str | None, str | None, str | None]:
    """Restituisce (fattura_id, movimento_id, contratto_id, riferimento_esterno)."""
    if riferimento_id.startswith("FATT-"):
        return riferimento_id, None, None, None
    if riferimento_id.startswith("MOV-"):
        return None, riferimento_id, None, None
    if riferimento_id.startswith("CTR-"):
        return None, None, riferimento_id, None
    if riferimento_id:
        return None, None, None, riferimento_id
    raise ValueError("riferimento_id vuoto")


def strip_front_matter(text: str) -> str:
    """Rimuove il blocco `---` iniziale e restituisce il corpo markdown."""
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4 :].strip()
    return text.strip()


def _clienti(r: Row) -> tuple:
    return (
        r["id"], r["denominazione"], r["partita_iva"], r["codice_fiscale"], r["indirizzo"],
        to_none(r["pec"]), to_none(r["sdi"]), r["settore"], to_pct(r["peso_fatturato"]),
    )  # fmt: skip


def _fornitori(r: Row) -> tuple:
    return (
        r["id"], r["denominazione"], r["partita_iva"], r["codice_fiscale"], r["indirizzo"],
        to_none(r["pec"]), to_none(r["sdi"]), r["categoria"],
    )  # fmt: skip


def _conti(r: Row) -> tuple:
    return (r["codice"], r["descrizione"], r["tipo"])


def _contratti(r: Row) -> tuple:
    cli, forn = split_controparte(r["controparte_id"])
    return (
        r["id"], r["tipo"], cli, forn, r["oggetto"], Decimal(r["importo"]), r["data_inizio"],
        r["data_fine"], to_bool(r["rinnovo"]), int(r["preavviso_giorni"]),
    )  # fmt: skip


def _fatture(r: Row) -> tuple:
    cli, forn = split_controparte(r["controparte_id"])
    return (
        r["id"], r["tipo"], r["numero"], r["data"], cli, forn,
        Decimal(r["imponibile"]), Decimal(r["iva"]), Decimal(r["totale"]), r["scadenza"],
    )  # fmt: skip


def _righe(r: Row) -> tuple:
    return (
        r["id"], r["fattura_id"], int(r["riga_numero"]), r["descrizione"], r["categoria"],
        Decimal(r["quantita"]), Decimal(r["prezzo"]), Decimal(r["imponibile"]),
    )  # fmt: skip


def _movimenti(r: Row) -> tuple:
    return (
        r["id"], r["data"], r["valuta"], Decimal(r["importo"]), r["causale"],
        Decimal(r["saldo"]), to_none(r["fattura_id"]),
    )  # fmt: skip


def _scritture(r: Row) -> tuple:
    fatt, mov, _ctr, ext = split_riferimento(r["riferimento_id"])
    return (
        r["id"], r["data"], r["transazione_id"], r["conto_codice"], Decimal(r["dare"]),
        Decimal(r["avere"]), r["descrizione"], fatt, mov, ext,
    )  # fmt: skip


def _scadenzario(r: Row) -> tuple:
    cli, forn = split_controparte(r["controparte_id"])
    fatt, _mov, ctr, ext = split_riferimento(r["riferimento_id"])
    return (
        r["id"], r["data"], r["tipo"], cli, forn, r["descrizione"], Decimal(r["importo"]),
        r["stato"], fatt, ctr, ext,
    )  # fmt: skip


def _documenti(r: Row) -> tuple:
    body = strip_front_matter((ROOT_DIR / r["file_path"]).read_text(encoding="utf-8"))
    return (
        r["doc_id"], r["tipo"], r["data"], r["titolo"], to_none(r["fornitore_id"]),
        to_none(r["cliente_id"]), r["file_path"], body,
    )  # fmt: skip


# (tabella, colonne, file relativo a DATA_DIR, funzione di conversione) in ordine di dipendenza FK
TABLES: list[tuple[str, str, str, Callable[[Row], tuple]]] = [
    (
        "clienti",
        (
            "id, denominazione, partita_iva, codice_fiscale, indirizzo, pec, sdi, settore, "
            "peso_fatturato_pct"
        ),
        "csv/clienti.csv",
        _clienti,
    ),
    (
        "fornitori",
        "id, denominazione, partita_iva, codice_fiscale, indirizzo, pec, sdi, categoria",
        "csv/fornitori.csv",
        _fornitori,
    ),
    ("piano_dei_conti", "codice, descrizione, tipo", "csv/piano_dei_conti.csv", _conti),
    (
        "documenti",
        "doc_id, tipo, data, titolo, fornitore_id, cliente_id, file_path, contenuto",
        "documenti/index.csv",
        _documenti,
    ),
    (
        "contratti",
        (
            "id, tipo, cliente_id, fornitore_id, oggetto, importo, data_inizio, data_fine, "
            "rinnovo, preavviso_giorni"
        ),
        "csv/contratti.csv",
        _contratti,
    ),
    (
        "fatture",
        "id, tipo, numero, data, cliente_id, fornitore_id, imponibile, iva, totale, scadenza",
        "csv/fatture.csv",
        _fatture,
    ),
    (
        "fatture_righe",
        "id, fattura_id, riga_numero, descrizione, conto_codice, quantita, prezzo, imponibile",
        "csv/fatture_righe.csv",
        _righe,
    ),
    (
        "movimenti_bancari",
        "id, data, valuta, importo, causale, saldo, fattura_id",
        "csv/movimenti_bancari.csv",
        _movimenti,
    ),
    (
        "scritture_contabili",
        (
            "id, data, transazione_id, conto_codice, dare, avere, descrizione, "
            "fattura_id, movimento_id, riferimento_esterno"
        ),
        "csv/scritture_contabili.csv",
        _scritture,
    ),
    (
        "scadenzario",
        (
            "id, data, tipo, cliente_id, fornitore_id, descrizione, importo, stato, "
            "fattura_id, contratto_id, riferimento_esterno"
        ),
        "csv/scadenzario.csv",
        _scadenzario,
    ),
]


def load_all(conn: psycopg.Connection) -> dict[str, int]:
    """Carica tutte le tabelle in un'unica transazione; restituisce i conteggi inseriti."""
    counts: dict[str, int] = {}
    with conn.transaction(), conn.cursor() as cur:
        for table, columns, rel_path, convert in TABLES:
            rows = [convert(r) for r in read_csv(DATA_DIR / rel_path)]
            placeholders = ", ".join(["%s"] * len(columns.split(",")))
            cur.executemany(f"INSERT INTO {table} ({columns}) VALUES ({placeholders})", rows)
            counts[table] = len(rows)
    return counts
