"""Costruzione del modello: per Gemini i 429 si ritentano nel client, senza far ripartire la run."""

from google.genai.types import HttpRetryOptions
from pydantic_ai.models import Model
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

from agentic_rag import config as app_config
from agentic_rag.agent import config

GOOGLE_PREFIX = "google:"
# Stessa cadenza del vecchio loop: 10, 20, 40, 60 s.
RETRY_429 = HttpRetryOptions(attempts=5, initial_delay=10, max_delay=60, http_status_codes=[429])


def build_model(name: str | None = None) -> Model | str:
    name = name or config.AGENT_MODEL
    if not name.startswith(GOOGLE_PREFIX):
        return name
    provider = GoogleProvider(api_key=app_config.GOOGLE_API_KEY or None, retry_options=RETRY_429)
    return GoogleModel(name.removeprefix(GOOGLE_PREFIX), provider=provider)
