"""Esecuzione delle indagini in background (task asyncio nello stesso processo).

Il DB è l'unica fonte di verità: il task scrive gli eventi, l'SSE li legge. Chiudere il browser
non ferma il task. Il codice DB resta sync (psycopg async non supporta il ProactorEventLoop di
Windows) e passa da `asyncio.to_thread`.
"""

import asyncio
import logging
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from pydantic_ai import AgentRunResultEvent
from pydantic_ai.agent.abstract import AgentRunEvents
from pydantic_ai.exceptions import (
    ModelHTTPError,
    RunCancelled,
    UnexpectedModelBehavior,
    UsageLimitExceeded,
)

from agentic_rag import config as app_config
from agentic_rag.agent import config as agent_config
from agentic_rag.agent.run import open_session, usage_limits
from agentic_rag.api import repository
from agentic_rag.api.events import tradurre
from agentic_rag.api.schemas import Errore, Interrotta, RispostaFinale

logger = logging.getLogger(__name__)

MOTIVO_STOP = "Fermata dall'utente"
MOTIVO_SHUTDOWN = "Server arrestato o riavviato"


class IndagineRunner:
    def __init__(self, max_concorrenti: int | None = None) -> None:
        self._sem = asyncio.Semaphore(max_concorrenti or app_config.MAX_INDAGINI_CONCORRENTI)
        self._tasks: dict[UUID, asyncio.Task[None]] = {}
        self._handles: dict[UUID, AgentRunEvents[Any]] = {}
        self._stop_richiesti: set[UUID] = set()

    async def avvia(self, domanda: str) -> UUID:
        id = await asyncio.to_thread(
            repository.run, repository.crea_indagine, domanda, agent_config.AGENT_MODEL
        )
        task = asyncio.create_task(self._esegui(id, domanda), name=f"indagine-{id}")
        self._tasks[id] = task
        task.add_done_callback(lambda _: self._tasks.pop(id, None))
        return id

    def stop(self, id: UUID) -> bool:
        """Chiede l'interruzione; False se l'indagine non è in esecuzione in questo processo."""
        handle = self._handles.get(id)
        if handle is not None:
            self._stop_richiesti.add(id)
            handle.cancel()  # la run termina con RunCancelled
            return True
        task = self._tasks.get(id)
        if task is not None and not task.done():  # ancora in coda (o sessione in apertura)
            self._stop_richiesti.add(id)
            task.cancel()
            return True
        return False

    async def chiudi(self) -> None:
        tasks = list(self._tasks.values())
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _esegui(self, id: UUID, domanda: str) -> None:
        conn = await asyncio.to_thread(repository.connect)
        seq = 0
        deps = None

        async def emit(evento: BaseModel) -> None:
            nonlocal seq
            seq += 1
            dati = evento.model_dump(mode="json", exclude={"tipo"})
            tipo = evento.model_dump()["tipo"]
            await asyncio.to_thread(repository.append_evento, conn, id, seq, tipo, dati)

        async def termina(stato: str, evento: BaseModel, **campi: Any) -> None:
            # stato ed evento terminale insieme (stessa transazione): lo stream SSE non può vedere
            # uno stato finale senza l'evento, e chi riceve l'evento trova lo stato già aggiornato
            nonlocal seq
            seq += 1
            dati = evento.model_dump(mode="json", exclude={"tipo"})
            tipo = evento.model_dump()["tipo"]
            await asyncio.to_thread(
                repository.concludi_con_evento, conn, id, stato, seq, tipo, dati, **campi
            )

        try:
            async with self._sem:
                await asyncio.to_thread(repository.segna_in_corso, conn, id)
                agent, deps = await asyncio.to_thread(open_session)
                async with agent.run_stream_events(
                    domanda, deps=deps, usage_limits=usage_limits()
                ) as events:
                    self._handles[id] = events
                    async for event in events:
                        if isinstance(event, AgentRunResultEvent):
                            risposta = event.result.output
                            u = event.result.usage
                            utilizzo = {
                                "requests": u.requests,
                                "tool_calls": u.tool_calls,
                                "input_tokens": u.input_tokens,
                                "output_tokens": u.output_tokens,
                            }
                            await termina(
                                "completata",
                                RispostaFinale(risposta=risposta),
                                risposta=risposta.model_dump(mode="json"),
                                utilizzo=utilizzo,
                            )
                        elif (evento := tradurre(event)) is not None:
                            await emit(evento)
        except RunCancelled:
            await termina("interrotta", Interrotta(motivo=MOTIVO_STOP), errore=MOTIVO_STOP)
        except asyncio.CancelledError:
            stop_utente = id in self._stop_richiesti
            motivo = MOTIVO_STOP if stop_utente else MOTIVO_SHUTDOWN
            await termina("interrotta", Interrotta(motivo=motivo), errore=motivo)
            if not stop_utente:
                raise
        except UsageLimitExceeded:
            await self._fallita(
                termina,
                "limite_richieste",
                f"L'agente ha superato il limite di {agent_config.AGENT_MAX_REQUESTS} chiamate "
                "al modello senza arrivare a una risposta.",
            )
        except UnexpectedModelBehavior:
            await self._fallita(
                termina,
                "risposta_non_valida",
                "Il modello non ha prodotto una risposta valida con fonti verificabili.",
            )
        except ModelHTTPError as e:
            await self._fallita(
                termina, "modello", f"Errore del servizio del modello (HTTP {e.status_code})."
            )
        except Exception as e:
            logger.exception("Indagine %s fallita", id)
            await self._fallita(termina, "interno", f"{type(e).__name__}: {e}")
        finally:
            self._handles.pop(id, None)
            self._stop_richiesti.discard(id)
            if deps is not None:
                await asyncio.to_thread(deps.conn.close)
            await asyncio.to_thread(conn.close)

    @staticmethod
    async def _fallita(termina: Any, errore: str, messaggio: str) -> None:
        await termina("fallita", Errore(errore=errore, messaggio=messaggio), errore=messaggio)
