"""Costruzione del modello: 429, 5xx ed errori di rete si ritentano nel wrapper (`ModelloGestito`),
non nel client del provider, così le attese sono misurate e la run non riparte."""

from pydantic_ai.models import Model
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

from agentic_rag import config as app_config
from agentic_rag.agent import config
from agentic_rag.agent.limiti import limitatore_per
from agentic_rag.agent.tentativi import ModelloGestito

GOOGLE_PREFIX = "google:"


def build_model(name: str | None = None, ruolo: str = "agente") -> Model:
    """Modello per nome. `ruolo` ("agente" o "giudice") sceglie i limiti RPM/TPM configurati."""
    name = name or config.AGENT_MODEL
    model: Model | str = name
    if name.startswith(GOOGLE_PREFIX):
        # senza retry_options il client non ritenta: i tentativi li fa ModelloGestito
        provider = GoogleProvider(api_key=app_config.GOOGLE_API_KEY or None)
        model = GoogleModel(name.removeprefix(GOOGLE_PREFIX), provider=provider)
    rpm, tpm = config.LIMITI.get(ruolo, (None, None))
    return ModelloGestito(model, limitatore_per(ruolo, name, rpm, tpm))
