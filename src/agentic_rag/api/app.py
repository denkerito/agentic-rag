"""API HTTP. Avvio: `uvicorn agentic_rag.api.app:app` (un solo worker: le run vivono nel processo)."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agentic_rag import config
from agentic_rag.api import repository
from agentic_rag.api.routes import router
from agentic_rag.api.runner import MOTIVO_SHUTDOWN, IndagineRunner


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    for name in ("DATABASE_URL_APP", "DATABASE_URL_AGENT"):
        if not getattr(config, name):
            raise RuntimeError(f"{name} non impostata (vedi .env.example)")
    # indagini rimaste in_coda/in_corso: il processo che le eseguiva non esiste più
    await asyncio.to_thread(repository.run, repository.interrompi_orfane, MOTIVO_SHUTDOWN)
    app.state.runner = IndagineRunner()
    yield
    await app.state.runner.chiudi()


def create_app() -> FastAPI:
    app = FastAPI(title="agentic-rag", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.CORS_ORIGINS,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = create_app()
