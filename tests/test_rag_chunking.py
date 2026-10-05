import csv
import re

import pytest

from agentic_rag.config import DATA_DIR, ROOT_DIR
from agentic_rag.db.load import strip_front_matter
from agentic_rag.rag import chunking
from agentic_rag.rag.chunking import (
    MAX_CHARS,
    MIN_CHARS,
    Documento,
    chunk_documento,
)
from agentic_rag.rag.embeddings import RateLimiter


def _doc(doc_id: str) -> tuple[str, str]:
    with (DATA_DIR / "documenti" / "index.csv").open(encoding="utf-8") as f:
        row = next(r for r in csv.DictReader(f) if r["doc_id"] == doc_id)
    body = strip_front_matter((ROOT_DIR / row["file_path"]).read_text(encoding="utf-8"))
    return row["tipo"], body


def test_contract_split_by_articolo() -> None:
    tipo, body = _doc("CTR-001")
    chunks = chunk_documento(tipo, body)
    assert len(chunks) == 10
    assert "Tra le parti" in chunks[0]
    assert any(c.startswith("### ARTICOLO 7") for c in chunks)


def test_contract_split_numbered_sections() -> None:
    tipo, body = _doc("CTR-009")
    chunks = chunk_documento(tipo, body)
    assert len(chunks) >= 2
    assert all(len(c) >= MIN_CHARS for c in chunks[1:])


def test_email_is_single_chunk() -> None:
    tipo, body = _doc("DOC-EML-001")
    assert chunk_documento(tipo, body) == [body.strip()]


def test_structured_type_without_headings_is_single_chunk() -> None:
    assert chunk_documento("contratto", "solo testo\n\nsenza sezioni") == [
        "solo testo\n\nsenza sezioni"
    ]


def test_short_sections_are_merged() -> None:
    body = "# T\n\n### A\nbreve\n\n### B\n" + "x" * 400
    chunks = chunk_documento("contratto", body)
    assert len(chunks) == 2
    assert chunks[0].startswith("# T") and "### A" in chunks[0]


def test_long_section_is_split_by_paragraphs() -> None:
    body = "### A\n" + "\n\n".join("p" * 900 for _ in range(5))
    chunks = chunk_documento("contratto", body)
    assert len(chunks) > 1
    assert all(len(c) <= MAX_CHARS for c in chunks)


def test_testo_per_embedding_header() -> None:
    doc = Documento("X", "email", "2025-01-01", "Titolo", "corpo", "Fornitore: ACME")
    text = chunking.testo_per_embedding(doc, "corpo")
    assert text == "Documento: Titolo (email, 2025-01-01)\nFornitore: ACME\n\ncorpo"
    no_cp = Documento("X", "email", "2025-01-01", "Titolo", "corpo")
    assert chunking.testo_per_embedding(no_cp, "corpo").count("\n") == 2


def test_all_documents_keep_every_heading() -> None:
    with (DATA_DIR / "documenti" / "index.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 62
    for r in rows:
        body = strip_front_matter((ROOT_DIR / r["file_path"]).read_text(encoding="utf-8"))
        chunks = chunk_documento(r["tipo"], body)
        assert chunks and all(c.strip() for c in chunks)
        joined = "\n".join(chunks)
        for heading in re.findall(r"(?m)^### .*$", body):
            assert heading in joined, (r["doc_id"], heading)


def test_rate_limiter_waits_when_window_is_full() -> None:
    now = [0.0]
    sleeps: list[float] = []

    def sleep(s: float) -> None:
        sleeps.append(s)
        now[0] += s

    limiter = RateLimiter(10, 1000, clock=lambda: now[0], sleep=sleep)
    limiter.acquire(6, 100)
    limiter.acquire(4, 100)  # esattamente al limite: nessuna attesa
    assert sleeps == []
    limiter.acquire(1, 10)  # supera i 10 rpm: attende la scadenza della finestra
    assert sum(sleeps) == pytest.approx(60, abs=1)


def test_rate_limiter_token_limit_and_oversize() -> None:
    now = [0.0]

    def sleep(s: float) -> None:
        now[0] += s

    limiter = RateLimiter(100, 500, clock=lambda: now[0], sleep=sleep)
    limiter.acquire(1, 400)
    limiter.acquire(1, 400)
    assert now[0] >= 60
    with pytest.raises(ValueError):
        limiter.acquire(1, 501)
