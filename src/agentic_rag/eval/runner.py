"""Esecuzione della batteria: una indagine per domanda, in sequenza, con pausa tra l'una e l'altra."""

import asyncio
import time
from collections import Counter
from collections.abc import Callable, Coroutine
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any, Literal

import psycopg
from google.genai import errors as genai_errors
from pydantic_ai import capture_run_messages
from pydantic_ai.exceptions import ModelAPIError, ModelHTTPError
from pydantic_ai.messages import ModelMessage, RetryPromptPart
from pydantic_ai.usage import RunUsage

from agentic_rag.agent.agent import MOTIVI_RIFIUTO
from agentic_rag.agent.limiti import MisuraAttese, misura_attese
from agentic_rag.agent.output import Risposta
from agentic_rag.agent.run import open_session, usage_limits
from agentic_rag.agent.tentativi import ERRORI_RETE
from agentic_rag.eval.fonti import sql_dell_agente, tabelle_lette
from agentic_rag.eval.giudice import giudica
from agentic_rag.eval.groundtruth import Domanda
from agentic_rag.eval.numeri import esegui_query_attesa
from agentic_rag.eval.valutazione import Esito, Giudizio, Valutazione, valuta

TIMEOUT_DOMANDA_S = 300.0  # secondi di lavoro dell'agente, attese del limitatore escluse
INTERVALLO_CONTROLLO_S = 0.2
TENTATIVI_GIUDICE = 2
# Errori del provider o della rete (ERRORI_RETE, la stessa definizione dei tentativi del modello):
# la domanda si riesegue. Superare il limite di richieste (UsageLimitExceeded) o il tempo di lavoro
# (TempoScaduto) è invece un fallimento dell'agente.

# Stato di un'esecuzione: `completata` ha un esito; `fallita_agente` è un insuccesso dell'agente
# (limite di richieste, risposta non valida, tempo di lavoro scaduto); `errore_infrastruttura`
# (rete, provider, database) non dice nulla sull'agente e lascia la combinazione da rifare.
Stato = Literal["completata", "fallita_agente", "errore_infrastruttura"]


class TempoScaduto(Exception):
    """Il tempo di lavoro dell'agente, al netto delle attese del limitatore, ha superato il limite."""


def errore_di_infrastruttura(e: BaseException) -> bool:
    """Rete, 429 o 5xx del provider, database: non dicono nulla sulla qualità dell'agente.

    Gli errori SQL dell'agente non arrivano qui: `query_sql` li restituisce al modello. Un errore
    psycopg che interrompe la run viene dal database (connessione persa, schema non pronto).
    """
    if isinstance(e, TempoScaduto):
        return False
    if isinstance(e, psycopg.Error):
        return True
    if isinstance(e, ModelHTTPError):
        return e.status_code == 429 or e.status_code >= 500
    if isinstance(e, genai_errors.APIError):
        return e.code == 429 or e.code >= 500
    return isinstance(e, (ModelAPIError, *ERRORI_RETE))


def nome_errore(e: BaseException) -> str:
    """Nome dell'eccezione, con il codice HTTP per gli errori del modello (es. `ModelHTTPError 503`)."""
    if isinstance(e, ModelHTTPError):
        return f"{type(e).__name__} {e.status_code}"
    return type(e).__name__


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
    durata_s: float = 0.0  # tempo reale dell'agente, giudice escluso
    errore_giudice: str | None = None
    rieseguita: bool = False  # primo tentativo fallito per un errore di infrastruttura
    infrastruttura: bool = (
        False  # errore di rete, provider o database (vedi errore_di_infrastruttura)
    )
    stato: Stato = "completata"
    token_input: int = 0
    token_output: int = 0
    attesa_s: float = 0.0  # secondi attesi: limitatore, pause e tentativi falliti del provider
    tentativi_provider: int = 0  # richieste al provider fallite e ritentate (429, 5xx, rete)
    rifiuti: dict[str, int] = field(default_factory=dict)  # risposte scartate dal validatore
    doc_recuperati: list[str] = field(default_factory=list)  # da ricerche e aperture

    @property
    def lavoro_s(self) -> float:
        return max(self.durata_s - self.attesa_s, 0.0)


async def entro_il_tempo[T](
    coro: Coroutine[Any, Any, T],
    timeout: float | None,
    misura: MisuraAttese,
    orologio: Callable[[], float] = time.monotonic,
) -> T:
    """Esegue `coro`; TempoScaduto se il tempo reale meno le attese del limitatore supera timeout."""
    task = asyncio.ensure_future(coro)
    inizio = orologio()
    try:
        while True:
            fatti, _ = await asyncio.wait({task}, timeout=INTERVALLO_CONTROLLO_S)
            if fatti:
                return task.result()
            if timeout is not None and orologio() - inizio - misura.secondi > timeout:
                raise TempoScaduto(f"oltre {timeout:.0f} s di lavoro")
    finally:
        if not task.done():
            task.cancel()
            with suppress(BaseException):
                await task


def rifiuti_del_validatore(messaggi: list[ModelMessage]) -> dict[str, int]:
    """Risposte finali scartate dal validatore delle fonti, per motivo."""
    conteggi: Counter[str] = Counter()
    for m in messaggi:
        for part in getattr(m, "parts", []):
            if isinstance(part, RetryPromptPart) and isinstance(part.content, str):
                for motivo, prefisso in MOTIVI_RIFIUTO.items():
                    if part.content.startswith(prefisso):
                        conteggi[motivo] += 1
    return dict(conteggi)


def documenti_recuperati(trace: list[dict[str, Any]]) -> list[str]:
    """Documenti restituiti da una ricerca o aperti. L'elenco per metadati non conta: elenca titoli."""
    out: set[str] = set()
    for ev in trace:
        if ev.get("kind") in ("cerca_testo", "cerca_semantica", "cerca_documenti"):
            out |= set(ev.get("doc_ids", []))
        elif ev.get("kind") == "apri_documento" and ev.get("doc_id"):
            out.add(str(ev["doc_id"]))
    return sorted(out)


def esegui_domanda(
    domanda: Domanda,
    model: str | None = None,
    judge: bool = False,
    judge_model: str | None = None,
    timeout: float | None = TIMEOUT_DOMANDA_S,
    ricerca_semantica: bool | None = None,  # None: RICERCA_SEMANTICA della configurazione
) -> RisultatoDomanda:
    inizio = time.monotonic()
    query_attesa = esegui_query_attesa(domanda.query_sql)
    try:
        agent, deps = open_session(model, ricerca_semantica)
    except (SystemExit, psycopg.Error) as e:  # configurazione mancante o database giù
        errore = (
            f"configurazione: {e}" if isinstance(e, SystemExit) else f"database: {type(e).__name__}"
        )
        return RisultatoDomanda(
            domanda, "errore", errore=errore, infrastruttura=True, stato="errore_infrastruttura"
        )
    # uso e messaggi si leggono anche se la run fallisce: una run interrotta dal validatore o dal
    # limite di richieste ha comunque consumato token e accumulato rifiuti
    usage = RunUsage()
    with misura_attese() as misura, capture_run_messages() as messaggi:
        try:
            result = asyncio.run(
                entro_il_tempo(
                    agent.run(domanda.domanda, deps=deps, usage_limits=usage_limits(), usage=usage),
                    timeout,
                    misura,
                )
            )
            durata = time.monotonic() - inizio
            risposta = result.output
            trace: list[dict[str, Any]] = list(deps.trace)
            seen_ids = set(deps.seen_ids)
        except Exception as e:  # noqa: BLE001 - la batteria deve proseguire con le domande successive
            infra = errore_di_infrastruttura(e)
            return RisultatoDomanda(
                domanda,
                "errore",
                errore=nome_errore(e),
                infrastruttura=infra,
                stato="errore_infrastruttura" if infra else "fallita_agente",
                sql_agente=sql_dell_agente(deps.trace),
                tabelle_lette=sorted(tabelle_lette(deps.trace)),
                richieste=usage.requests,
                passi_tool=len(deps.trace),
                durata_s=time.monotonic() - inizio,
                token_input=usage.input_tokens or 0,
                token_output=usage.output_tokens or 0,
                attesa_s=misura.secondi,
                tentativi_provider=misura.tentativi_falliti,
                rifiuti=rifiuti_del_validatore(messaggi),
                doc_recuperati=documenti_recuperati(deps.trace),
            )
        finally:
            deps.conn.close()

    giudizio: Giudizio | None = None
    errore_giudice: str | None = None
    if judge and domanda.risposta_attesa:
        for _ in range(TENTATIVI_GIUDICE):
            try:
                giudizio = giudica(domanda.domanda, domanda.risposta_attesa, risposta, judge_model)
                errore_giudice = None
                break
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
        richieste=usage.requests,
        passi_tool=len(trace),
        durata_s=durata,
        errore_giudice=errore_giudice,
        token_input=usage.input_tokens or 0,
        token_output=usage.output_tokens or 0,
        attesa_s=misura.secondi,
        tentativi_provider=misura.tentativi_falliti,
        rifiuti=rifiuti_del_validatore(messaggi),
        doc_recuperati=documenti_recuperati(trace),
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
    ricerca_semantica: bool | None = None,
) -> list[RisultatoDomanda]:
    """Esegue le domande in sequenza. `risultati` è un accumulatore opzionale: se la batteria viene
    interrotta (Ctrl+C) chi chiama ha comunque le domande già completate."""
    risultati = risultati if risultati is not None else []
    for i, d in enumerate(domande):
        if inizio:
            inizio(d)
        r = esegui_domanda(d, model, judge, judge_model, timeout, ricerca_semantica)
        if r.esito == "errore" and r.infrastruttura:
            if pausa:
                dormi(pausa)
            r = esegui_domanda(d, model, judge, judge_model, timeout, ricerca_semantica)
            r.rieseguita = True
        risultati.append(r)
        if progresso:
            progresso(r)
        if pausa and i < len(domande) - 1:
            dormi(pausa)  # i limiti del piano gratuito: ~7 richieste al modello per domanda
    return risultati
