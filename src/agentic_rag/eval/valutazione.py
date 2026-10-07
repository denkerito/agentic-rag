"""Esito di una domanda: combina fonti, numeri, comportamento e (se attivo) giudizio."""

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel

from agentic_rag.agent.output import Risposta
from agentic_rag.eval.fonti import MetricheFonti, valuta_fonti
from agentic_rag.eval.groundtruth import Domanda, Modalita
from agentic_rag.eval.numeri import MetricheNumeri, RisultatoQuery, valuta_numeri

# Soglie (euristiche, da affinare guardando il report privato)
SOGLIA_FONTI = 1.0
SOGLIA_NUMERI = 1.0

Esito = Literal["ok", "ko", "errore", "nd"]


class Giudizio(BaseModel):
    verdetto: Literal["corretta", "parziale", "errata"]
    motivazione: str


@dataclass
class Comportamento:
    ok: bool
    motivo: str  # riservato al report privato


def controlla_comportamento(modalita: Modalita, risposta: Risposta) -> Comportamento | None:
    if modalita == Modalita.ONESTA:
        ok = not risposta.causa_documentata and bool(risposta.limiti)
        return Comportamento(ok, "causa_documentata=False e limiti valorizzati")
    if modalita == Modalita.NON_RISPONDIBILE:
        ok = (
            not risposta.causa_documentata
            and bool(risposta.limiti)
            and risposta.confidenza != "alta"
            and not risposta.numeri
        )
        return Comportamento(
            ok, "causa non documentata, limiti, confidenza non alta, nessun numero"
        )
    return None


@dataclass
class Valutazione:
    fonti: MetricheFonti
    numeri: MetricheNumeri
    comportamento: Comportamento | None
    giudizio: Giudizio | None
    esito: Esito


def calcola_esito(
    modalita: Modalita,
    fonti: MetricheFonti,
    numeri: MetricheNumeri,
    comportamento: Comportamento | None,
    giudizio: Giudizio | None,
) -> Esito:
    controlli: list[bool] = []
    if comportamento is not None:
        controlli.append(comportamento.ok)
    # Fonti e numeri contano per le domande che hanno una risposta da trovare.
    if modalita in (Modalita.NORMALE, Modalita.REGOLARE):
        if fonti.id_recall is not None:
            controlli.append(fonti.id_recall >= SOGLIA_FONTI)
        if fonti.tabelle_recall is not None:
            controlli.append(fonti.tabelle_recall >= SOGLIA_FONTI)
        if numeri.recall is not None:
            controlli.append(numeri.recall >= SOGLIA_NUMERI)
    if giudizio is not None:
        controlli.append(giudizio.verdetto != "errata")
    if not controlli:
        return "nd"  # nessun controllo applicabile: non si dichiara né ok né ko
    return "ok" if all(controlli) else "ko"


def valuta(
    domanda: Domanda,
    risposta: Risposta,
    trace: list[dict[str, Any]],
    seen_ids: set[str],
    query_attesa: RisultatoQuery | None,
    giudizio: Giudizio | None = None,
) -> Valutazione:
    fonti = valuta_fonti(domanda, risposta, trace, seen_ids)
    numeri = valuta_numeri(query_attesa, risposta)
    comportamento = controlla_comportamento(domanda.modalita, risposta)
    return Valutazione(
        fonti=fonti,
        numeri=numeri,
        comportamento=comportamento,
        giudizio=giudizio,
        esito=calcola_esito(domanda.modalita, fonti, numeri, comportamento, giudizio),
    )
