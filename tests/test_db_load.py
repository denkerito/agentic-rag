from decimal import Decimal

import pytest

from agentic_rag.db.load import (
    split_controparte,
    split_riferimento,
    strip_front_matter,
    to_bool,
    to_none,
    to_pct,
)


def test_to_pct() -> None:
    assert to_pct("30%") == Decimal(30)


def test_to_bool_and_none() -> None:
    assert to_bool("True") is True
    assert to_bool("False") is False
    assert to_none("") is None
    assert to_none("x") == "x"


def test_split_controparte() -> None:
    assert split_controparte("CLI-001") == ("CLI-001", None)
    assert split_controparte("FOR-002") == (None, "FOR-002")
    assert split_controparte("") == (None, None)
    with pytest.raises(ValueError):
        split_controparte("XXX-1")


def test_split_riferimento() -> None:
    assert split_riferimento("FATT-A-2025-0001") == ("FATT-A-2025-0001", None, None, None)
    assert split_riferimento("MOV-000001") == (None, "MOV-000001", None, None)
    assert split_riferimento("CTR-001") == (None, None, "CTR-001", None)
    assert split_riferimento("PAGA-2025-01") == (None, None, None, "PAGA-2025-01")


def test_strip_front_matter() -> None:
    assert strip_front_matter('---\ndoc_id: "X"\n---\n\n# Titolo\ntesto') == "# Titolo\ntesto"
    assert strip_front_matter("senza front matter") == "senza front matter"
