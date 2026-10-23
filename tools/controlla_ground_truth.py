"""Controllo strutturale di un ground truth: stampa solo conteggi, mai testi, ID o valori.

Uso: python tools/controlla_ground_truth.py eval/ground_truth_finale

Si può mostrare l'output all'assistente: non contiene il contenuto del test set.
Segnala le domande con ID inesistenti nei dati, query attese in errore, senza numeri o con più di
25 valori (il controllo sui numeri non si applica), e fonti non riconosciute.
"""

import sys
from collections import Counter
from pathlib import Path

from agentic_rag.agent.ids import extract_ids
from agentic_rag.eval.groundtruth import carica
from agentic_rag.eval.numeri import MAX_VALORI_ATTESI, esegui_query_attesa


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Uso: python tools/controlla_ground_truth.py <cartella del ground truth>")
    noti: set[str] = set()
    for f in [*Path("data/csv").glob("*.csv"), Path("data/index.csv")]:
        noti |= extract_ids(f.read_text(encoding="utf-8"))
    gt = carica(Path(sys.argv[1]))
    modalita = Counter(d.modalita.value for d in gt.domande)
    print(f"domande: {len(gt.domande)} | modalità: {dict(modalita)}")
    da_controllare = 0
    for d in gt.domande:
        inesistenti = len((set(d.id_attesi) | extract_ids(d.risposta_attesa)) - noti)
        q = esegui_query_attesa(d.query_sql)
        if q is None:
            valori: str | int = "assente"
        elif q.errore:
            valori = "ERRORE"
        else:
            valori = len(q.valori)
        problema = (
            inesistenti
            or valori == "ERRORE"
            or (isinstance(valori, int) and (valori == 0 or valori > MAX_VALORI_ATTESI))
            or d.fonti_non_riconosciute
        )
        da_controllare += bool(problema)
        print(
            f"#{d.id:>3} {d.modalita.value:<17} ID attesi {len(d.id_attesi):>2} "
            f"(inesistenti {inesistenti}) tabelle {len(d.tabelle_attese)} "
            f"non riconosciute {len(d.fonti_non_riconosciute)} valori query {valori}"
            f"{'  <-- controlla' if problema else ''}"
        )
    print(f"domande da controllare: {da_controllare}")


if __name__ == "__main__":
    main()
