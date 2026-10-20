"""Righe per esecuzione degli esperimenti: pubblica (conteggi, mai il ground truth) e privata.

Ogni riga contiene i dati grezzi da cui `riepilogo` calcola le metriche: per i nomi e le definizioni
vedi docs/superpowers/specs/2026-10-19-harness-esperimenti-design.md.
"""

from datetime import datetime
from typing import Any

from agentic_rag.agent.agent import DOC_PREFIXES
from agentic_rag.eval.groundtruth import Domanda, Modalita
from agentic_rag.eval.report import riga_privata, riga_pubblica
from agentic_rag.eval.runner import RisultatoDomanda

MODALITA_NON_DOCUMENTATA = (Modalita.ONESTA, Modalita.NON_RISPONDIBILE)


def documenti_attesi(d: Domanda) -> list[str]:
    return [i for i in d.id_attesi if i.startswith(DOC_PREFIXES)]


def causa_attesa(d: Domanda) -> str | None:
    """Dalla sola struttura del ground truth: la causa è documentata, non documentata o n/a."""
    if d.modalita in MODALITA_NON_DOCUMENTATA:
        return "non_documentata"
    if d.modalita == Modalita.NORMALE and documenti_attesi(d):
        return "documentata"
    return None


def conteggi(r: RisultatoDomanda) -> dict[str, Any]:
    """Numeratori e denominatori delle metriche (solo numeri: nessun valore del ground truth)."""
    d = r.domanda
    v = r.valutazione
    attesi_doc = set(documenti_attesi(d))
    out: dict[str, Any] = {
        "fonti_attese": len(d.id_attesi),
        "fonti_trovate": v.fonti.id_trovati if v else None,
        "numeri_attesi": v.numeri.attesi if v and v.numeri.applicabile else None,
        "numeri_trovati": v.numeri.trovati if v and v.numeri.applicabile else None,
        "documenti_attesi": len(attesi_doc),
        "documenti_recuperati": len(attesi_doc & set(r.doc_recuperati)),
        "causa_attesa": causa_attesa(d),
        "causa_dichiarata_documentata": r.risposta.causa_documentata if r.risposta else None,
        "giudice": v.giudizio.verdetto if v and v.giudizio else None,
        "citate_non_viste": v.fonti.citate_non_viste if v else None,
    }
    return out


def _base(r: RisultatoDomanda, variante: str, ripetizione: int, tentativo: int) -> dict[str, Any]:
    return {
        "variante": variante,
        "ripetizione": ripetizione,
        "tentativo": tentativo,
        "stato": r.stato,
        "quando": datetime.now().astimezone().isoformat(timespec="seconds"),
        "token_input": r.token_input,
        "token_output": r.token_output,
        "attesa_s": round(r.attesa_s, 1),
        "tentativi_provider": r.tentativi_provider,
        "lavoro_s": round(r.lavoro_s, 1),
        "rifiuti": r.rifiuti,
        "conteggi": conteggi(r),
    }


def riga_esecuzione_pubblica(
    r: RisultatoDomanda, variante: str, ripetizione: int, tentativo: int
) -> dict[str, Any]:
    return _base(r, variante, ripetizione, tentativo) | riga_pubblica(r)


def riga_esecuzione_privata(
    r: RisultatoDomanda, variante: str, ripetizione: int, tentativo: int
) -> dict[str, Any]:
    return _base(r, variante, ripetizione, tentativo) | riga_privata(r)
