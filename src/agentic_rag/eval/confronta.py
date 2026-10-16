"""Confronto tra le varianti di un esperimento (con e senza ricerca semantica) sui report pubblici.

Uso: python -m agentic_rag.eval.confronta --etichetta esp-ricerca-a

Legge solo i report pubblici (`eval/reports/*.json`), mai la cartella privata. Il criterio è fissato
nel documento di design prima dell'esperimento: la ricerca semantica resta solo se la variante che la
usa ottiene almeno SOGLIA_PUNTI punti percentuali in più di esiti `ok`.
"""

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentic_rag.eval.report import REPORTS_DIR

SOGLIA_PUNTI = 10.0
# Una domanda il cui giudice è fallito non ha il controllo sulla causa: non conta come `ok`.
GIUDICE_MANCANTE = "giudice_mancante"


@dataclass
class Variante:
    ricerca_semantica: bool
    report: int = 0
    esiti: Counter[str] = field(default_factory=Counter)
    ok_per_domanda: dict[int, list[bool]] = field(default_factory=lambda: defaultdict(list))
    rieseguite: int = 0
    richieste: list[int] = field(default_factory=list)
    durate: list[float] = field(default_factory=list)

    @property
    def esecuzioni(self) -> int:
        return sum(self.esiti.values())

    @property
    def ok_pct(self) -> float:
        return 100 * self.esiti["ok"] / self.esecuzioni if self.esecuzioni else 0.0


def carica(cartella: Path, etichetta: str) -> list[dict[str, Any]]:
    """Report pubblici dell'esperimento. Glob non ricorsivo: la sottocartella privata resta fuori."""
    out = []
    for path in sorted(cartella.glob("*.json")):
        corpo = json.loads(path.read_text(encoding="utf-8"))
        meta = corpo.get("meta", {})
        if meta.get("etichetta") != etichetta:
            continue
        if meta.get("interrotta"):
            print(f"Escluso {path.name}: batteria interrotta")
            continue
        out.append(corpo)
    return out


def controlla_omogenei(report: list[dict[str, Any]]) -> None:
    """Tutte le esecuzioni devono usare lo stesso modello e lo stesso giudice."""
    for chiave in ("modello", "giudice"):
        valori = {r["meta"].get(chiave) for r in report}
        if len(valori) > 1:
            raise ValueError(f"Report con {chiave} diversi: {sorted(map(str, valori))}")


def riepiloga(report: list[dict[str, Any]]) -> dict[bool, Variante]:
    varianti: dict[bool, Variante] = {}
    for corpo in report:
        semantica = bool(corpo["meta"].get("ricerca_semantica", True))
        v = varianti.setdefault(semantica, Variante(semantica))
        v.report += 1
        for d in corpo["domande"]:
            esito = GIUDICE_MANCANTE if d.get("errore_giudice") else d["esito"]
            v.esiti[esito] += 1
            v.ok_per_domanda[d["id"]].append(esito == "ok")
            v.rieseguite += bool(d.get("rieseguita"))
            if d["esito"] != "errore":
                v.richieste.append(d["richieste"])
                v.durate.append(d["durata_s"])
    return varianti


def verdetto(varianti: dict[bool, Variante]) -> str:
    if set(varianti) != {True, False}:
        return "Verdetto non disponibile: servono entrambe le varianti."
    delta = varianti[True].ok_pct - varianti[False].ok_pct
    if delta >= SOGLIA_PUNTI:
        return f"La ricerca semantica RESTA: +{delta:.1f} punti di ok (soglia {SOGLIA_PUNTI:.0f})."
    return (
        f"La ricerca semantica NON supera la soglia: {delta:+.1f} punti di ok "
        f"(soglia {SOGLIA_PUNTI:.0f}). Vince la variante più semplice, senza vettori."
    )


def _media(valori: list[float] | list[int]) -> str:
    return f"{sum(valori) / len(valori):.1f}" if valori else "-"


def righe(varianti: dict[bool, Variante]) -> list[str]:
    out: list[str] = []
    ordine = [varianti[k] for k in (True, False) if k in varianti]
    for v in ordine:
        nome = "con ricerca semantica" if v.ricerca_semantica else "senza ricerca semantica"
        esiti = ", ".join(f"{k} {n}" for k, n in sorted(v.esiti.items()))
        out += [
            f"== {nome}: {v.report} report, {v.esecuzioni} esecuzioni",
            f"   ok {v.esiti['ok']}/{v.esecuzioni} ({v.ok_pct:.1f}%) · {esiti}",
            (
                f"   rieseguite {v.rieseguite} · richieste medie {_media(v.richieste)} · "
                f"durata media {_media(v.durate)} s"
            ),
        ]
    domande = sorted({i for v in ordine for i in v.ok_per_domanda})
    if domande:
        out.append("")
        out.append(
            "domanda  "
            + "  ".join(f"{'con' if v.ricerca_semantica else 'senza':>6}" for v in ordine)
        )
        for i in domande:
            celle = []
            for v in ordine:
                esiti_d = v.ok_per_domanda.get(i, [])
                celle.append(f"{sum(esiti_d)}/{len(esiti_d)}".rjust(6))
            out.append(f"#{i:<7} " + "  ".join(celle))
    out += ["", verdetto(varianti)]
    return out


def main() -> None:
    p = argparse.ArgumentParser(prog="python -m agentic_rag.eval.confronta", description=__doc__)
    p.add_argument("--etichetta", required=True, help="etichetta dell'esperimento (--etichetta)")
    p.add_argument(
        "--cartella", type=Path, default=REPORTS_DIR, help="cartella dei report pubblici"
    )
    args = p.parse_args()
    report = carica(args.cartella, args.etichetta)
    if not report:
        raise SystemExit(f"Nessun report con etichetta {args.etichetta!r} in {args.cartella}")
    try:
        controlla_omogenei(report)
    except ValueError as e:
        raise SystemExit(str(e)) from e
    print("\n".join(righe(riepiloga(report))))


if __name__ == "__main__":
    main()
