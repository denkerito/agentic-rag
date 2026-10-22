"""Parametri dell'agente (sovrascrivibili da .env dove indicato)."""

import os

import agentic_rag.config  # noqa: F401  (carica .env)

AGENT_MODEL: str = os.getenv("AGENT_MODEL", "openrouter:anthropic/claude-haiku-5.5")
JUDGE_MODEL: str = os.getenv("JUDGE_MODEL", "openrouter:anthropic/claude-sonnet-5.5")
# Modelli via OpenRouter: costanti (non variabili d'ambiente), così l'hash di src/ nel manifesto
# degli esperimenti le copre. Provider fissato: riproducibilità e letture dalla cache.
OPENROUTER_PROVIDER: dict = {"order": ["anthropic"], "allow_fallbacks": False}
# Effort per ruolo: None lascia il default del modello.
EFFORT: dict[str, str | None] = {"agente": None, "giudice": "medium"}
MAX_TOKENS_RISPOSTA: int = 16_000  # tetto per risposta (ragionamento compreso): si paga l'uso
AGENT_MAX_REQUESTS: int = int(
    os.getenv("AGENT_MAX_REQUESTS", "25")
)  # chiamate al modello per domanda
# Un risultato di query_sql è intero oppure un'anteprima dichiarata, mai un pezzo che sembra il tutto.
# Soglia in caratteri del JSON restituito, tarata sulle 302 SQL delle batterie del 2026-10-22: p99 a
# 25.643, solo 2 oltre i 30.000 (873 e 132 righe). Circa 10.000 token nel caso peggiore.
SQL_MAX_CARATTERI: int = 30_000
SQL_RIGHE_ANTEPRIMA: int = 5  # righe d'esempio di un'anteprima
SQL_RIGHE_LETTE: int = 5_000  # tetto di lettura per contare e profilare
SQL_MAX_CELL_CHARS: int = 300
DOC_MAX_CHARS: int = 6000
SEARCH_MAX_K: int = 8
# Distanza coseno oltre la quale un chunk è considerato non pertinente. Calibrata a mano su
# gemini-embedding-2 con query non del test set: pertinenti 0.20-0.24 (altri chunk pertinenti fino
# a ~0.31), aziendali ma assenti dai documenti ≥ 0.32, fuori tema ≥ 0.43. La soglia esclude le
# "assenti": una ricerca senza riscontro deve restituire nulla, non il documento più simile.
SEARCH_MAX_DISTANCE: float = float(os.getenv("SEARCH_MAX_DISTANCE", "0.30"))
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
# limite. I 429 e 5xx li ritenta ModelloGestito (tentativi.py).
LIMITI: dict[str, tuple[int | None, int | None]] = {
    "agente": (_intero("AGENT_RPM"), _intero("AGENT_TPM")),
    "giudice": (_intero("JUDGE_RPM"), _intero("JUDGE_TPM")),
}
