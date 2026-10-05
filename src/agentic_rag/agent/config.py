"""Parametri dell'agente (sovrascrivibili da .env dove indicato)."""

import os

import agentic_rag.config  # noqa: F401  (carica .env)

AGENT_MODEL: str = os.getenv("AGENT_MODEL", "google:gemini-3.5-flash-lite")
AGENT_MAX_REQUESTS: int = int(
    os.getenv("AGENT_MAX_REQUESTS", "25")
)  # chiamate al modello per domanda
SQL_MAX_ROWS: int = 50
SQL_MAX_CELL_CHARS: int = 300
DOC_MAX_CHARS: int = 6000
SEARCH_MAX_K: int = 8
# Distanza coseno oltre la quale un chunk è considerato non pertinente. Calibrata a mano:
# query pertinenti ≤ 0.37, query fuori tema ≥ 0.41. Da riverificare con l'eval.
SEARCH_MAX_DISTANCE: float = float(os.getenv("SEARCH_MAX_DISTANCE", "0.38"))
