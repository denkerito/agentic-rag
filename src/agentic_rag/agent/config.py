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
# Ricerca semantica (tool `cerca_semantica`): spegnibile per l'ablazione (RICERCA_SEMANTICA=0).
RICERCA_SEMANTICA: bool = os.getenv("RICERCA_SEMANTICA", "1").strip().lower() not in (
    "0",
    "false",
    "no",
    "off",
)
ELENCO_PER_PAGINA: int = 30  # documenti per pagina di `elenca_documenti`
TESTO_MAX_K: int = 8  # risultati massimi di `cerca_testo`


def _intero(nome: str) -> int | None:
    valore = os.getenv(nome, "").strip()
    return int(valore) if valore else None


# Limiti di richieste/minuto e token/minuto per agente e giudice (opzionali): non impostati = nessun
# limite. I 429 e 5xx restano gestiti dai tentativi del client del provider.
LIMITI: dict[str, tuple[int | None, int | None]] = {
    "agente": (_intero("AGENT_RPM"), _intero("AGENT_TPM")),
    "giudice": (_intero("JUDGE_RPM"), _intero("JUDGE_TPM")),
}
