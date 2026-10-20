"""Costruzione del modello: per Gemini 429 e 5xx si ritentano nel client, senza far ripartire la run."""

from google.genai.types import HttpRetryOptions
from pydantic_ai.models import Model
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

from agentic_rag import config as app_config
from agentic_rag.agent import config
from agentic_rag.agent.limiti import limitatore_per
from agentic_rag.agent.tentativi import ModelloGestito

GOOGLE_PREFIX = "google:"
# Stessa cadenza del vecchio loop: 10, 20, 40, 60 s. Oltre ai 429 (quota) si ritentano gli errori
# temporanei del servizio (500/502/503/504, es. modello sovraccarico).
RETRY_429 = HttpRetryOptions(
    attempts=5, initial_delay=10, max_delay=60, http_status_codes=[429, 500, 502, 503, 504]
)


def build_model(name: str | None = None, ruolo: str = "agente") -> Model | str:
    """Modello per nome. `ruolo` ("agente" o "giudice") sceglie i limiti RPM/TPM configurati."""
    name = name or config.AGENT_MODEL
    model: Model | str = name
    if name.startswith(GOOGLE_PREFIX):
        provider = GoogleProvider(
            api_key=app_config.GOOGLE_API_KEY or None, retry_options=RETRY_429
        )
        model = GoogleModel(name.removeprefix(GOOGLE_PREFIX), provider=provider)
    rpm, tpm = config.LIMITI.get(ruolo, (None, None))
    limitatore = limitatore_per(ruolo, name, rpm, tpm)
    return ModelloGestito(model, limitatore) if limitatore else model
