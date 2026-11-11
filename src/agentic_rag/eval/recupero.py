"""Benchmark del recupero: precision@k, recall@k e MRR della ricerca semantica e di quella testuale.

    python -m agentic_rag.eval.recupero --gt eval/ground_truth --nome sviluppo

Misura i due strumenti di ricerca, non l'agente: ogni domanda con almeno un documento atteso
(`DOC-*`, `CTR-*`) diventa una ricerca con il testo della domanda, e i pertinenti sono i documenti
attesi. L'agente invece riformula le ricerche e ne fa più d'una: questi numeri spiegano il
componente, non il risultato delle indagini. Il report contiene solo aggregati.
"""

import argparse
import json
import re
import sys
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

import psycopg

from agentic_rag import config as app_config
from agentic_rag.agent import config as agent_config
from agentic_rag.agent.tools import HEADLINE_OPZIONI, TESTO_SQL
from agentic_rag.eval.groundtruth import GROUND_TRUTH_DIR, carica
from agentic_rag.eval.metriche import documenti_attesi
from agentic_rag.eval.report import REPORTS_DIR
from agentic_rag.eval.statistica import bootstrap, bootstrap_appaiato
from agentic_rag.rag.search import search_chunks

K = (1, 3, 5)
PROFONDITA = 10  # documenti per classifica, e cutoff dell'MRR
CHUNK_LETTI = (
    40  # chunk letti per avere almeno PROFONDITA documenti distinti (98 chunk, 62 documenti)
)
SISTEMI = ("semantica", "semantica_soglia", "testuale")
RIFERIMENTO = "testuale"
NOMI = {
    "semantica": "Semantica",
    "semantica_soglia": f"Semantica con soglia ({agent_config.SEARCH_MAX_DISTANCE:g})",
    "testuale": "Testuale (full-text)",
}


# --- Metriche per domanda: funzioni pure -----------------------------------------------------------


def precision_at_k(classifica: list[str], pertinenti: set[str], k: int) -> float:
    """Pertinenti nei primi k ÷ k: anche i posti vuoti di una classifica corta contano come errori."""
    return len(set(classifica[:k]) & pertinenti) / k


def recall_at_k(classifica: list[str], pertinenti: set[str], k: int) -> float:
    return len(set(classifica[:k]) & pertinenti) / len(pertinenti)


def reciprocal_rank(classifica: list[str], pertinenti: set[str]) -> float:
    """1 / posizione del primo pertinente nei primi PROFONDITA; 0 se non c'è."""
    for i, doc in enumerate(classifica[:PROFONDITA]):
        if doc in pertinenti:
            return 1 / (i + 1)
    return 0.0


METRICHE: dict[str, Callable[[list[str], set[str]], float]] = {
    **{f"p@{k}": (lambda c, p, k=k: precision_at_k(c, p, k)) for k in K},
    **{f"r@{k}": (lambda c, p, k=k: recall_at_k(c, p, k)) for k in K},
    "mrr": reciprocal_rank,
}


def documenti_in_ordine(doc_ids: Iterable[str]) -> list[str]:
    """Documenti senza ripetizioni, nell'ordine del loro chunk migliore."""
    return list(dict.fromkeys(doc_ids))


def query_or(testo: str) -> str:
    """Le parole della domanda unite da `or`, come il tool `cerca_testo` suggerisce all'agente."""
    return " or ".join(re.findall(r"\w+", testo))


# --- Classifiche sul database ----------------------------------------------------------------------


def classifiche(conn: psycopg.Connection, domanda: str) -> dict[str, list[str]]:
    """Le tre classifiche di documenti per una domanda: un solo embedding per le due semantiche."""
    hits = search_chunks(conn, domanda, CHUNK_LETTI)
    pertinenti = [h for h in hits if h.distanza <= agent_config.SEARCH_MAX_DISTANCE]
    righe = conn.execute(
        TESTO_SQL,
        {
            "tipo": None,
            "data_da": None,
            "data_a": None,
            "fornitore_id": None,
            "cliente_id": None,
            "query": query_or(domanda),
            "k": PROFONDITA,
            "opzioni": HEADLINE_OPZIONI,
        },
    ).fetchall()
    return {
        "semantica": documenti_in_ordine(h.doc_id for h in hits)[:PROFONDITA],
        "semantica_soglia": documenti_in_ordine(h.doc_id for h in pertinenti)[:PROFONDITA],
        "testuale": [r[0] for r in righe],
    }


# --- Aggregazione e report -------------------------------------------------------------------------


def misura(
    classifiche_per_sistema: dict[str, dict[int, list[str]]],
    pertinenti: dict[int, set[str]],
    riferimento: str = RIFERIMENTO,
) -> dict[str, Any]:
    """Media sulle domande con IC 95% per sistema, e differenze appaiate rispetto al riferimento."""
    per_domanda = {
        s: {m: {i: f(c[i], pertinenti[i]) for i in pertinenti} for m, f in METRICHE.items()}
        for s, c in classifiche_per_sistema.items()
    }
    return {
        "domande": len(pertinenti),
        "pertinenti_medi": sum(map(len, pertinenti.values())) / len(pertinenti),
        "sistemi": {
            s: {m: vars(bootstrap(list(v.values()))) for m, v in metriche.items()}
            for s, metriche in per_domanda.items()
        },
        "differenze": {
            f"{s} - {riferimento}": {
                m: vars(bootstrap_appaiato(per_domanda[s][m], per_domanda[riferimento][m]))
                for m in METRICHE
            }
            for s in per_domanda
            if s != riferimento
        },
    }


def _cella(s: dict[str, Any], segno: bool = False) -> str:
    if s["valore"] is None:
        return "n/a"
    f = "{:+.2f}" if segno else "{:.2f}"
    return f"{f.format(s['valore'])} [{f.format(s['basso'])}, {f.format(s['alto'])}]"


def markdown(nome: str, gt: Path, out: dict[str, Any]) -> str:
    sistemi = list(out["sistemi"])
    righe = [
        f"# Benchmark del recupero: {nome}",
        "",
        (
            f"- ground truth: `{gt.as_posix()}` · domande con documenti attesi: {out['domande']} · "
            f"documenti pertinenti per domanda: {out['pertinenti_medi']:.1f}"
        ),
        f"- classifiche per documento, primi {PROFONDITA}; la ricerca usa il testo della domanda",
        "",
        "## Metriche (media sulle domande, IC 95% bootstrap)",
        "",
        "| Metrica | " + " | ".join(NOMI[s] for s in sistemi) + " |",
        "|---|" + "---|" * len(sistemi),
    ]
    for m in METRICHE:
        righe.append(f"| {m} | " + " | ".join(_cella(out["sistemi"][s][m]) for s in sistemi) + " |")
    diff = list(out["differenze"])
    righe += [
        "",
        "## Differenze appaiate (IC 95%)",
        "",
        "| Metrica | " + " | ".join(diff) + " |",
        "|---|" + "---|" * len(diff),
    ]
    for m in METRICHE:
        righe.append(
            f"| {m} | "
            + " | ".join(_cella(out["differenze"][d][m], segno=True) for d in diff)
            + " |"
        )
    righe += [
        "",
        "Note:",
        (
            f"- la precision@k ha un massimo pari a pertinenti ÷ k: con "
            f"{out['pertinenti_medi']:.1f} documenti pertinenti in media, p@5 non può avvicinarsi a 1;"
        ),
        (
            "- i pertinenti sono solo i documenti *necessari* del ground truth: un documento utile "
            "ma non elencato conta come errore, quindi la precision è sottostimata;"
        ),
        (
            "- la ricerca con soglia restituisce solo i passaggi sotto la distanza di pertinenza, "
            "come vede l'agente: può restituire meno di k documenti, e i posti vuoti contano come "
            "errori;"
        ),
        (
            "- misura gli strumenti con il testo della domanda: l'agente riformula le ricerche e ne "
            "fa più d'una, quindi questi numeri non sono il risultato delle indagini."
        ),
    ]
    return "\n".join(righe) + "\n"


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):  # console Windows
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(prog="python -m agentic_rag.eval.recupero", description=__doc__)
    p.add_argument("--gt", type=Path, default=GROUND_TRUTH_DIR, help="cartella del ground truth")
    p.add_argument("--nome", required=True, help="nome del report (es. sviluppo, finale)")
    p.add_argument("--out", type=Path, default=REPORTS_DIR / "recupero")
    args = p.parse_args()

    domande = [d for d in carica(args.gt).domande if documenti_attesi(d)]
    if not domande:
        raise SystemExit("Nessuna domanda con documenti attesi.")
    pertinenti = {d.id: set(documenti_attesi(d)) for d in domande}
    per_sistema: dict[str, dict[int, list[str]]] = {s: {} for s in SISTEMI}
    with psycopg.connect(app_config.DATABASE_URL_AGENT, connect_timeout=10) as conn:
        for d in domande:
            for s, docs in classifiche(conn, d.domanda).items():
                per_sistema[s][d.id] = docs
    out = misura(per_sistema, pertinenti)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / f"{args.nome}.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    md = markdown(args.nome, args.gt, out)
    (args.out / f"{args.nome}.md").write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
