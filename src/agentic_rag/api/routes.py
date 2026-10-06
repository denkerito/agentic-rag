import asyncio
from collections.abc import AsyncIterable
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.sse import EventSourceResponse, ServerSentEvent

from agentic_rag.api import repository
from agentic_rag.api.runner import IndagineRunner
from agentic_rag.api.schemas import (
    STATI_FINALI,
    TIPI_TERMINALI,
    IndagineCreata,
    IndagineCreate,
    IndagineDettaglio,
    IndagineRiga,
)

router = APIRouter(prefix="/indagini", tags=["indagini"])

POLL_SECONDI = 0.5


def get_runner(request: Request) -> IndagineRunner:
    return request.app.state.runner


async def indagine_esistente(id: UUID) -> UUID:
    if await asyncio.to_thread(repository.run, repository.stato, id) is None:
        raise HTTPException(404, "Indagine inesistente")
    return id


@router.post("", status_code=202)
async def avvia(
    body: IndagineCreate, runner: Annotated[IndagineRunner, Depends(get_runner)]
) -> IndagineCreata:
    id = await runner.avvia(body.domanda)
    return IndagineCreata(id=id, stato="in_coda")


@router.get("")
async def elenca(
    limit: Annotated[int, Query(ge=1, le=100)] = 20, before: datetime | None = None
) -> list[IndagineRiga]:
    rows = await asyncio.to_thread(repository.run, repository.lista, limit, before)
    return [IndagineRiga.model_validate(r) for r in rows]


@router.get("/{id}")
async def dettaglio(id: UUID) -> IndagineDettaglio:
    row = await asyncio.to_thread(repository.run, repository.dettaglio, id)
    if row is None:
        raise HTTPException(404, "Indagine inesistente")
    return IndagineDettaglio.model_validate(row)


@router.post("/{id}/stop", status_code=202)
async def ferma(id: UUID, runner: Annotated[IndagineRunner, Depends(get_runner)]) -> dict:
    await indagine_esistente(id)
    if not runner.stop(id):
        raise HTTPException(409, "L'indagine non è in corso")
    return {"id": id, "stop": "richiesto"}


@router.get(
    "/{id}/eventi",
    response_class=EventSourceResponse,
    dependencies=[Depends(indagine_esistente)],
)
async def eventi(
    id: UUID,
    last_event_id: Annotated[int | None, Header()] = None,
    dopo: int | None = None,
) -> AsyncIterable[ServerSentEvent]:
    """Replay degli eventi con `seq` > Last-Event-ID (o `?dopo=`), poi coda live.

    Si chiude dopo l'evento terminale (risposta, errore, interrotta).
    """
    ultimo = last_event_id if last_event_id is not None else (dopo or 0)
    conn = await asyncio.to_thread(repository.connect)
    try:
        while True:
            rows = await asyncio.to_thread(repository.eventi_dopo, conn, id, ultimo)
            for r in rows:
                ultimo = r["seq"]
                yield ServerSentEvent(data=r["dati"], event=r["tipo"], id=str(r["seq"]))
                if r["tipo"] in TIPI_TERMINALI:
                    return
            if rows:
                continue
            stato = await asyncio.to_thread(repository.stato, conn, id)
            if stato in STATI_FINALI:
                # stato finale senza evento terminale visto: ultima lettura, poi chiudi
                for r in await asyncio.to_thread(repository.eventi_dopo, conn, id, ultimo):
                    yield ServerSentEvent(data=r["dati"], event=r["tipo"], id=str(r["seq"]))
                return
            await asyncio.sleep(POLL_SECONDI)
    finally:
        conn.close()
