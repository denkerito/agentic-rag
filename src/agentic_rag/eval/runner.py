"""Esecuzione della batteria: una indagine per domanda, in sequenza, con pausa tra l'una e l'altra."""

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import psycopg

from agentic_rag.agent.output import Risposta
from agentic_rag.agent.run import open_session, usage_limits
from agentic_rag.eval.fonti import sql_dell_agente, tabelle_lette
from agentic_rag.eval.giudice import giudica
from agentic_rag.eval.groundtruth import Domanda
from agentic_rag.eval.numeri import esegui_query_attesa
from agentic_rag.eval.valutazione import Esito, Giudizio, Valutazione, valuta

TIMEOUT_DOMANDA_S = 300.0


@dataclass
class RisultatoDomanda:
    domanda: Domanda
    esito: Esito
    risposta: Risposta | None = None
    errore: str | None = None  # nome dell'eccezione, non il messaggio
    valutazione: Valutazione | None = None
    sql_agente: list[str] = field(default_factory=list)
    tabelle_lette: list[str] = field(default_factory=list)
    richieste: int = 0
    passi_tool: int = 0  # chiamate a tool eseguite: dice se l'agente stava avanzando o era fermo
    durata_s: float = 0.0
    errore_giudice: str | None = None


def esegui_domanda(
    domanda: Domanda,
    model: str | None = None,
    judge: bool = False,
    judge_model: str | None = None,
    timeout: float | None = TIMEOUT_DOMANDA_S,
) -> RisultatoDomanda:
    inizio = time.monotonic()
    query_attesa = esegui_query_attesa(domanda.query_sql)
    try:
        agent, deps = open_session(model)
    except SystemExit as e:  # configurazione mancante (DATABASE_URL_AGENT)
        return RisultatoDomanda(domanda, "errore", errore=f"configurazione: {e}")
    except psycopg.Error as e:
        return RisultatoDomanda(domanda, "errore", errore=f"database: {type(e).__name__}")
    try:
        # asyncio.wait_for: un'indagine bloccata (rete, 429 a ripetizione) non ferma la batteria
        result = asyncio.run(
            asyncio.wait_for(
                agent.run(domanda.domanda, deps=deps, usage_limits=usage_limits()), timeout
            )
        )
        risposta = result.output
        trace: list[dict[str, Any]] = list(deps.trace)
        seen_ids = set(deps.seen_ids)
        richieste = result.usage.requests
    except Exception as e:  # noqa: BLE001 - la batteria deve proseguire con le domande successive
        return RisultatoDomanda(
            domanda,
            "errore",
            errore=type(e).__name__,
            sql_agente=sql_dell_agente(deps.trace),
            tabelle_lette=sorted(tabelle_lette(deps.trace)),
            passi_tool=len(deps.trace),
            durata_s=time.monotonic() - inizio,
        )
    finally:
        deps.conn.close()

    giudizio: Giudizio | None = None
    errore_giudice: str | None = None
    if judge and domanda.risposta_attesa:
        try:
            giudizio = giudica(domanda.domanda, domanda.risposta_attesa, risposta, judge_model)
        except Exception as e:  # noqa: BLE001 - il giudice non deve far perdere la domanda
            errore_giudice = type(e).__name__

    val = valuta(domanda, risposta, trace, seen_ids, query_attesa, giudizio)
    return RisultatoDomanda(
        domanda=domanda,
        esito=val.esito,
        risposta=risposta,
        valutazione=val,
        sql_agente=sql_dell_agente(trace),
        tabelle_lette=sorted(tabelle_lette(trace)),
        richieste=richieste,
        passi_tool=len(trace),
        durata_s=time.monotonic() - inizio,
        errore_giudice=errore_giudice,
    )


def esegui(
    domande: list[Domanda],
    model: str | None = None,
    judge: bool = False,
    judge_model: str | None = None,
    pausa: float = 8.0,
    timeout: float | None = TIMEOUT_DOMANDA_S,
    inizio: Callable[[Domanda], None] | None = None,
    progresso: Callable[[RisultatoDomanda], None] | None = None,
    dormi: Callable[[float], None] = time.sleep,
    risultati: list[RisultatoDomanda] | None = None,
) -> list[RisultatoDomanda]:
    """Esegue le domande in sequenza. `risultati` è un accumulatore opzionale: se la batteria viene
    interrotta (Ctrl+C) chi chiama ha comunque le domande già completate."""
    risultati = risultati if risultati is not None else []
    for i, d in enumerate(domande):
        if inizio:
            inizio(d)
        r = esegui_domanda(d, model, judge, judge_model, timeout)
        risultati.append(r)
        if progresso:
            progresso(r)
        if pausa and i < len(domande) - 1:
            dormi(pausa)  # i limiti del piano gratuito: ~7 richieste al modello per domanda
    return risultati
