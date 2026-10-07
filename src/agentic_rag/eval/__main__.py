"""Uso: python -m agentic_rag.eval [--dry-run] [--ids 1,2] [--storia ST-01] [--judge] ...

La console stampa solo il report pubblico; quello privato (con il ground truth) va in
eval/reports/private/ ed è ignorato da git: non va condiviso con l'assistente di sviluppo.
"""

import argparse
from datetime import datetime
from pathlib import Path

from agentic_rag.agent import config as agent_config
from agentic_rag.eval import report
from agentic_rag.eval.groundtruth import GROUND_TRUTH_DIR, GroundTruth, Modalita, carica
from agentic_rag.eval.numeri import esegui_query_attesa
from agentic_rag.eval.runner import RisultatoDomanda, esegui


def _filtra(gt: GroundTruth, args: argparse.Namespace) -> list:
    domande = gt.domande
    if args.ids:
        ids = {int(x) for x in args.ids.split(",")}
        domande = [d for d in domande if d.id in ids]
    if args.storia:
        domande = [d for d in domande if d.storia_chiave == args.storia]
    if args.modalita:
        domande = [d for d in domande if d.modalita == Modalita(args.modalita)]
    return domande


def dry_run(gt: GroundTruth, domande: list) -> None:
    """Solo struttura: nessuna chiamata al modello, nessun valore del ground truth."""
    print(
        f"Ground truth: {len(gt.domande)} domande, {len(gt.storie)} storie ({len(domande)} selezionate)"
    )
    for d in domande:
        q = esegui_query_attesa(d.query_sql)
        if q is None:
            query = "assente"
        elif q.errore:
            query = f"ERRORE ({q.errore})"
        else:
            query = f"ok ({q.n_righe} righe, {len(q.valori)} valori numerici)"
        storia = (
            "collegata"
            if gt.storia_nota(d)
            else ("riconosciuta ma non in storie" if d.storia_chiave else "generica")
        )
        print(
            f"#{d.id:>2} modalità {d.modalita.value:<17} storia {storia:<30} "
            f"fonti: {len(d.id_attesi)} ID, {len(d.tabelle_attese)} tabelle, "
            f"{len(d.fonti_non_riconosciute)} non riconosciute; query attesa: {query}"
        )


def main() -> None:
    p = argparse.ArgumentParser(prog="python -m agentic_rag.eval", description=__doc__)
    p.add_argument(
        "--dry-run", action="store_true", help="valida il ground truth, senza chiamare il modello"
    )
    p.add_argument("--ids", help="id delle domande, separati da virgola")
    p.add_argument("--storia", help="solo le domande di una storia (es. ST-01)")
    p.add_argument("--modalita", choices=[m.value for m in Modalita])
    p.add_argument("--model", help=f"modello dell'agente (default {agent_config.AGENT_MODEL})")
    p.add_argument(
        "--pause", type=float, default=8.0, help="secondi tra una domanda e la successiva"
    )
    p.add_argument("--judge", action="store_true", help="giudice LLM sulla correttezza della causa")
    p.add_argument("--judge-model", help="modello del giudice (default: lo stesso dell'agente)")
    p.add_argument("--gt", type=Path, default=GROUND_TRUTH_DIR, help="cartella del ground truth")
    p.add_argument("--out", type=Path, default=report.REPORTS_DIR, help="cartella dei report")
    args = p.parse_args()

    gt = carica(args.gt)
    domande = _filtra(gt, args)
    if not domande:
        raise SystemExit("Nessuna domanda selezionata.")
    if args.dry_run:
        dry_run(gt, domande)
        return

    def progresso(r: RisultatoDomanda) -> None:
        print(
            f"#{r.domanda.id:>2} {r.esito} ({r.richieste} richieste, {r.durata_s:.0f} s)",
            flush=True,
        )

    risultati = esegui(
        domande,
        model=args.model,
        judge=args.judge,
        judge_model=args.judge_model,
        pausa=args.pause,
        progresso=progresso,
    )
    meta = {
        "data": datetime.now().astimezone().isoformat(timespec="seconds"),
        "modello": args.model or agent_config.AGENT_MODEL,
        "giudice": (args.judge_model or args.model or agent_config.AGENT_MODEL)
        if args.judge
        else "spento",
        "domande": len(domande),
    }
    percorsi, righe = report.scrivi(risultati, meta, args.out)
    print()
    print("\n".join(righe))
    print(f"\nReport pubblico: {percorsi['pubblico_md']}")
    print(f"Report privato (NON condividere): {percorsi['privato_md']}")


if __name__ == "__main__":
    main()
