"""Validazione del giudice LLM: foglio di etichettatura umana (privato, alla cieca) e κ di Cohen.

Il foglio contiene la risposta attesa, quindi resta in eval/reports/private/. Il verdetto del giudice
non compare nel foglio: chi etichetta non deve esserne influenzato. Nel riepilogo pubblico finiscono
solo κ e accordo.
"""

import csv
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

from agentic_rag.eval.statistica import SEME, kappa_cohen

FOGLIO = "etichette.csv"
CLASSI = ("corretta", "parziale", "errata")
COLONNE = [
    "chiave",
    "domanda",
    "risposta_attesa",
    "conclusione_agente",
    "causa_documentata",
    "limiti",
    "etichetta_umana",
]


def _chiave(r: dict[str, Any]) -> str:
    return f"{r['variante']}|{r['ripetizione']}|{r['id']}"


def _giudicate(priv: Path) -> list[dict[str, Any]]:
    """Esecuzioni completate con un verdetto del giudice (l'ultima per combinazione)."""
    path = priv / "esecuzioni.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"nessuna esecuzione in {path}")
    righe = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    per_chiave = {
        _chiave(r): r
        for r in righe
        if r["stato"] == "completata" and r["conteggi"]["giudice"] and r.get("risposta")
    }
    return list(per_chiave.values())


def campione_stratificato(
    righe: list[dict[str, Any]], n: int, seme: int = SEME
) -> list[dict[str, Any]]:
    """Fino a n righe, a giro tra gli strati (modalità, variante), con ordine casuale ma fisso."""
    rng = random.Random(seme)
    strati: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in sorted(righe, key=_chiave):
        strati[(r["modalita"], r["variante"])].append(r)
    for s in strati.values():
        rng.shuffle(s)
    out: list[dict[str, Any]] = []
    code = [strati[k] for k in sorted(strati)]
    while len(out) < n and any(code):
        for c in code:
            if c and len(out) < n:
                out.append(c.pop())
    return out


def esporta(priv: Path, n: int) -> tuple[Path, int]:
    scelte = campione_stratificato(_giudicate(priv), n)
    path = priv / FOGLIO
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLONNE)
        w.writeheader()
        for r in scelte:
            ris = r["risposta"]
            w.writerow(
                {
                    "chiave": _chiave(r),
                    "domanda": r["domanda"],
                    "risposta_attesa": r["risposta_attesa"],
                    "conclusione_agente": ris["conclusione"],
                    "causa_documentata": ris["causa_documentata"],
                    "limiti": ris["limiti"] or "",
                    "etichetta_umana": "",
                }
            )
    return path, len(scelte)


def calcola_kappa(priv: Path) -> dict[str, Any]:
    """κ tra etichette umane e verdetti del giudice, sulle righe etichettate del foglio."""
    giudice = {_chiave(r): r["conteggi"]["giudice"] for r in _giudicate(priv)}
    with (priv / FOGLIO).open(encoding="utf-8", newline="") as f:
        etichettate = [
            (r["chiave"], r["etichetta_umana"].strip().lower())
            for r in csv.DictReader(f)
            if r["etichetta_umana"].strip().lower() in CLASSI
        ]
    coppie = [(umana, giudice[k]) for k, umana in etichettate if k in giudice]
    if not coppie:
        raise ValueError("nessuna riga etichettata (valori ammessi: corretta, parziale, errata)")
    umane = [u for u, _ in coppie]
    verdetti = [g for _, g in coppie]

    def binario(xs: list[str]) -> list[str]:
        return ["corretta" if x == "corretta" else "non corretta" for x in xs]

    k3 = kappa_cohen(umane, verdetti)
    k2 = kappa_cohen(binario(umane), binario(verdetti))
    return {
        "campione": len(coppie),
        "kappa_3_classi": None if k3 is None else round(k3, 2),
        "kappa_binario": None if k2 is None else round(k2, 2),
        "accordo": sum(u == g for u, g in coppie) / len(coppie),
    }
