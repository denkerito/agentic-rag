"""Esecuzione della batteria: una indagine per domanda, in sequenza, con pausa tra l'una e l'altra."""

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from agentic_rag.agent.output import Risposta
from agentic_rag.agent.run import open_session, usage_limits
from agentic_rag.eval.fonti import sql_dell_agente, tabelle_lette
from agentic_rag.eval.giudice import giudica
from agentic_rag.eval.groundtruth import Domanda
from agentic_rag.eval.numeri import esegui_query_attesa
from agentic_rag.eval.valutazione import Esito, Giudizio, Valutazione, valuta


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
    durata_s: float = 0.0
    errore_giudice: str | None = None


def esegui_domanda(
    domanda: Domanda,
    model: str | None = None,
    judge: bool = False,
    judge_model: str | None = None,
) -> RisultatoDomanda:
    inizio = time.monotonic()
    query_attesa = esegui_query_attesa(domanda.query_sql)
    try:
        agent, deps = open_session(model)
    except SystemExit as e:  # configurazione mancante (DATABASE_URL_AGENT)
        return RisultatoDomanda(domanda, "errore", errore=f"configurazione: {e}")
    try:
        result = agent.run_sync(domanda.domanda, deps=deps, usage_limits=usage_limits())
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
            errore_giudice = type(e).__name__  # il giudice non deve far perdere la domanda

    val = valuta(domanda, risposta, trace, seen_ids, query_attesa, giudizio)
    return RisultatoDomanda(
        domanda=domanda,
        esito=val.esito,
        risposta=risposta,
        valutazione=val,
        sql_agente=sql_dell_agente(trace),
        tabelle_lette=sorted(tabelle_lette(trace)),
        richieste=richieste,
        durata_s=time.monotonic() - inizio,
        errore_giudice=errore_giudice,
    )


def esegui(
    domande: list[Domanda],
    model: str | None = None,
    judge: bool = False,
    judge_model: str | None = None,
    pausa: float = 8.0,
    progresso: Callable[[RisultatoDomanda], None] | None = None,
    dormi: Callable[[float], None] = time.sleep,
) -> list[RisultatoDomanda]:
    risultati: list[RisultatoDomanda] = []
    for i, d in enumerate(domande):
        r = esegui_domanda(d, model, judge, judge_model)
        risultati.append(r)
        if progresso:
            progresso(r)
        if pausa and i < len(domande) - 1:
            dormi(pausa)  # i limiti del piano gratuito: ~7 richieste al modello per domanda
    return risultati
