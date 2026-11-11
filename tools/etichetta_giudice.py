"""Etichettatura umana del giudice nel terminale, una risposta alla volta: niente fogli di calcolo.

Uso: python tools/etichetta_giudice.py [--etichetta finale] [--campione 30] [--rivedi]

Se il foglio privato non esiste lo crea, come `esperimento etichette`. Mostra domanda, risposta
attesa e risposta dell'agente, mai il verdetto del giudice: l'etichettatura resta alla cieca. Ogni
etichetta si salva subito, quindi si può uscire e riprendere. Il contenuto è privato: non va
incollato all'assistente.
"""

import argparse
import csv
import os
import sys
import textwrap
from pathlib import Path

from agentic_rag.eval import etichette
from agentic_rag.eval.esperimento import cartelle

TASTI = {"c": "corretta", "p": "parziale", "e": "errata"}
LARGHEZZA = 100
CRITERI = """\
corretta: stessa causa o esito e dati essenziali della risposta attesa
parziale: solo una parte della causa o dei dati, oppure giusta ma incompleta
errata:   causa diversa, contraddice la risposta attesa, o inventa una causa «non documentata»"""


def leggi(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def salva(path: Path, righe: list[dict[str, str]]) -> None:
    """Riscrive il foglio con le stesse colonne: prima un file temporaneo, poi la sostituzione."""
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=etichette.COLONNE)
        w.writeheader()
        w.writerows(righe)
    os.replace(tmp, path)


def etichettata(r: dict[str, str]) -> bool:
    return r["etichetta_umana"].strip().lower() in etichette.CLASSI


def blocco(titolo: str, testo: str) -> str:
    righe = [textwrap.fill(p, LARGHEZZA - 2) if p.strip() else "" for p in testo.splitlines()]
    return f"{titolo}\n" + textwrap.indent("\n".join(righe).strip() or "(vuoto)", "  ")


def scheda(r: dict[str, str], posizione: int, totale: int) -> str:
    causa = {"True": "sì", "False": "no"}.get(r["causa_documentata"], r["causa_documentata"])
    parti = [
        f"Risposta {posizione} di {totale}" + "  ·  " + "-" * 40,
        blocco("DOMANDA", r["domanda"]),
        blocco("RISPOSTA ATTESA", r["risposta_attesa"]),
        blocco("RISPOSTA DELL'AGENTE", r["conclusione_agente"]),
        f"Causa dichiarata documentata: {causa}",
        blocco("LIMITI DICHIARATI", r["limiti"] or "nessuno"),
        "-" * 60,
        CRITERI,
    ]
    if etichettata(r):
        parti.append(f"Etichetta attuale: {r['etichetta_umana']} (Invio per tenerla)")
    return "\n\n".join(parti)


def pulisci() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def main(argv: list[str] | None = None) -> None:
    if hasattr(sys.stdout, "reconfigure"):  # console Windows: accenti e «»
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--etichetta", default="finale")
    p.add_argument("--campione", type=int, default=30, help="solo se il foglio va creato")
    p.add_argument(
        "--rivedi", action="store_true", help="ripassa anche le risposte già etichettate"
    )
    p.add_argument(
        "--foglio", type=Path, help="un foglio diverso da quello dell'esperimento (prove)"
    )
    args = p.parse_args(argv)

    if args.foglio:
        path = args.foglio
    else:
        _, priv = cartelle(args.etichetta)
        path = priv / etichette.FOGLIO
        if not path.exists():
            path, n = etichette.esporta(priv, args.campione)
            print(f"Creato il foglio con {n} risposte.")
    righe = leggi(path)
    indici = [i for i, r in enumerate(righe) if args.rivedi or not etichettata(r)]
    domanda = "[c] corretta  [p] parziale  [e] errata  [s] salta  [q] esci  > "
    for i in indici:
        pulisci()
        print(scheda(righe[i], i + 1, len(righe)))
        while True:
            scelta = input("\n" + domanda).strip().lower()
            if scelta in TASTI:
                righe[i]["etichetta_umana"] = TASTI[scelta]
                salva(path, righe)
                break
            if scelta == "s" or (scelta == "" and etichettata(righe[i])):
                break
            if scelta == "q":
                print(f"\nSalvato: {sum(map(etichettata, righe))} di {len(righe)} etichettate.")
                print("Rilancia lo stesso comando per riprendere da dove sei rimasto.")
                return
            print("Scrivi c, p, e, s oppure q.")
    pulisci()
    fatte = sum(map(etichettata, righe))
    print(f"Etichettate {fatte} di {len(righe)}.")
    if fatte < len(righe):
        print("Ne mancano alcune (saltate): rilancia lo stesso comando per completarle.")
    else:
        print(
            "Tutte fatte. Ora calcola l'accordo con il giudice:\n"
            f"  .\\.venv\\Scripts\\python.exe -m agentic_rag.eval.esperimento kappa "
            f"--etichetta {args.etichetta}"
        )


if __name__ == "__main__":
    main()
