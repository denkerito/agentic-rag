"""Riconoscimento degli ID di fonte (FATT-*, MOV-*, CTR-*, DOC-*, ...)."""

import re

ID_PATTERN = re.compile(
    r"\b(?:FATT-[AP]-\d{4}-\d{4}|MOV-\d{6}|SCR-\d{6}|RIG-\d{4}|SCD-\d{4}|"
    r"CTR-\d{3}|CLI-\d{3}|FOR-\d{3}|DOC-[A-Z]{3}-\d{3})\b"
)


def extract_ids(text: str) -> set[str]:
    return set(ID_PATTERN.findall(text))
