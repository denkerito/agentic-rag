"""Chunking per struttura dei documenti (funzioni pure, nessun I/O)."""

import re
from dataclasses import dataclass

MIN_CHARS = 250
MAX_CHARS = 2000
STRUCTURED_TYPES = {"contratto", "addendum"}


@dataclass(frozen=True)
class Documento:
    doc_id: str
    tipo: str
    data: str
    titolo: str
    contenuto: str
    controparte: str | None = None  # es. "Fornitore: Nimbus Software S.r.l."


def _split_long(piece: str) -> list[str]:
    """Rete di sicurezza: divide per paragrafi un pezzo oltre MAX_CHARS."""
    if len(piece) <= MAX_CHARS:
        return [piece]
    out: list[str] = []
    current = ""
    for para in piece.split("\n\n"):
        if current and len(current) + len(para) + 2 > MAX_CHARS:
            out.append(current)
            current = para
        else:
            current = f"{current}\n\n{para}" if current else para
    if current:
        out.append(current)
    return out


def chunk_documento(tipo: str, contenuto: str) -> list[str]:
    """Contratti/addendum: una sezione `###` per chunk (sezioni corte accorpate); altro: intero."""
    body = contenuto.strip()
    if tipo not in STRUCTURED_TYPES or not re.search(r"(?m)^### ", body):
        return [body]

    pieces = [p.strip() for p in re.split(r"(?m)^(?=### )", body) if p.strip()]
    merged: list[str] = []
    for piece in pieces:
        if merged and len(piece) < MIN_CHARS:
            merged[-1] = f"{merged[-1]}\n\n{piece}"
        else:
            merged.append(piece)
    return [part for piece in merged for part in _split_long(piece)]


def testo_per_embedding(doc: Documento, testo: str) -> str:
    """Testo da embeddare: intestazione di contesto + chunk. Non viene salvato nel DB."""
    lines = [f"Documento: {doc.titolo} ({doc.tipo}, {doc.data})"]
    if doc.controparte:
        lines.append(doc.controparte)
    return "\n".join(lines) + f"\n\n{testo}"
