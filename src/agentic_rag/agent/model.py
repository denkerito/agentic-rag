"""Costruzione del modello: 429, 5xx ed errori di rete si ritentano nel wrapper (`ModelloGestito`),
non nel client del provider, così le attese sono misurate e la run non riparte."""

from collections.abc import Coroutine
from contextlib import suppress
from typing import Any

from openai import AsyncOpenAI
from pydantic_ai.models import Model
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.openrouter import OpenRouterModel, OpenRouterModelSettings
from pydantic_ai.models.wrapper import WrapperModel
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.providers.openrouter import OpenRouterProvider

from agentic_rag import config as app_config
from agentic_rag.agent import config
from agentic_rag.agent.limiti import limitatore_per
from agentic_rag.agent.tentativi import ModelloGestito

GOOGLE_PREFIX = "google:"
OPENROUTER_PREFIX = "openrouter:"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def impostazioni_openrouter(ruolo: str) -> OpenRouterModelSettings:
    """Cache su istruzioni, tool e ultimo messaggio; provider fissato; costo nella risposta."""
    impostazioni = OpenRouterModelSettings(
        openrouter_cache_instructions=True,
        openrouter_cache_tool_definitions=True,
        openrouter_cache_messages=True,
        openrouter_provider=config.OPENROUTER_PROVIDER,
        openrouter_usage={"include": True},
        max_tokens=config.MAX_TOKENS_RISPOSTA,
    )
    if effort := config.EFFORT.get(ruolo):
        impostazioni["openrouter_reasoning"] = {"effort": effort}
    return impostazioni


def _openrouter(nome: str, ruolo: str) -> OpenRouterModel:
    if not app_config.OPENROUTER_API_KEY:
        raise SystemExit("OPENROUTER_API_KEY non impostata (vedi .env.example)")
    # max_retries=0: i tentativi li fa ModelloGestito
    client = AsyncOpenAI(
        base_url=OPENROUTER_BASE_URL, api_key=app_config.OPENROUTER_API_KEY, max_retries=0
    )
    return OpenRouterModel(
        nome,
        provider=OpenRouterProvider(openai_client=client),
        settings=impostazioni_openrouter(ruolo),
    )


async def chiudi_client(model: Model) -> None:
    """Chiude il client OpenAI-compatibile del modello nel ciclo di eventi in cui è stato usato.

    Il provider chiude solo un client HTTP suo, non l'AsyncOpenAI che gli passiamo. Senza chiusura,
    il __del__ dell'SDK lo chiude nel ciclo che gira quando passa il garbage collector: con un
    asyncio.run per domanda (eval) è quello della domanda successiva, e la chiusura fallisce con
    "Event loop is closed". Con modelli senza client OpenAI non fa niente.
    """
    while isinstance(model, WrapperModel):
        model = model.wrapped
    client = getattr(model, "client", None)
    if isinstance(client, AsyncOpenAI):
        await client.close()


async def poi_chiudi[T](coro: Coroutine[Any, Any, T], model: Model) -> T:
    """Esegue `coro` e chiude il client del modello nello stesso ciclo di eventi: l'eval ne apre uno
    per domanda (agente) e uno per verdetto (giudice). Un errore di chiusura non cambia l'esito."""
    try:
        return await coro
    finally:
        with suppress(Exception):
            await chiudi_client(model)


def build_model(name: str | None = None, ruolo: str = "agente") -> Model:
    """Modello per nome. `ruolo` ("agente" o "giudice") sceglie limiti RPM/TPM ed effort."""
    name = name or config.AGENT_MODEL
    model: Model | str = name
    if name.startswith(GOOGLE_PREFIX):
        # senza retry_options il client non ritenta: i tentativi li fa ModelloGestito
        provider = GoogleProvider(api_key=app_config.GOOGLE_API_KEY or None)
        model = GoogleModel(name.removeprefix(GOOGLE_PREFIX), provider=provider)
    elif name.startswith(OPENROUTER_PREFIX):
        model = _openrouter(name.removeprefix(OPENROUTER_PREFIX), ruolo)
    rpm, tpm = config.LIMITI.get(ruolo, (None, None))
    return ModelloGestito(model, limitatore_per(ruolo, name, rpm, tpm))
