"""Esperimenti: varianti × ripetizioni × domande, con ripresa e riepilogo statistico.

    python -m agentic_rag.eval.esperimento esegui --etichetta X \\
        --variante con:semantica=1 --variante senza:semantica=0 --ripetizioni 5 --judge \\
        [--criterio "task_success_rate:con-senza>=10"]
    python -m agentic_rag.eval.esperimento esegui --etichetta X      # ripresa
    python -m agentic_rag.eval.esperimento riepilogo --etichetta X
    python -m agentic_rag.eval.esperimento etichette --etichetta X --campione 30
    python -m agentic_rag.eval.esperimento kappa --etichetta X

Ogni esecuzione è scritta su disco appena conclusa; rilanciare `esegui` riprende dalle combinazioni
(variante, ripetizione, domanda) non ancora chiuse. Design:
docs/superpowers/specs/2026-10-19-harness-esperimenti-design.md.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from agentic_rag import config as app_config
from agentic_rag.agent import config as agent_config
from agentic_rag.eval import etichette, riepilogo
from agentic_rag.eval.ambiente import controlla_ambiente
from agentic_rag.eval.groundtruth import GROUND_TRUTH_DIR, Domanda, carica
from agentic_rag.eval.metriche import riga_esecuzione_privata, riga_esecuzione_pubblica
from agentic_rag.eval.report import PRIVATE_SUBDIR, REPORTS_DIR
from agentic_rag.eval.runner import (
    TIMEOUT_DOMANDA_S,
    ErroreFatale,
    RisultatoDomanda,
    esegui_domanda,
)

CHIAVI_VARIANTE = {"modello", "semantica"}
TENTATIVI_FINALI = 2
PAUSA_S = 5.0


class ErroreEsperimento(Exception):
    """Configurazione o stato dell'esperimento non coerente: il messaggio è per l'utente."""


# --- Percorsi e file ------------------------------------------------------------------------------


def cartelle(etichetta: str, base: Path = REPORTS_DIR) -> tuple[Path, Path]:
    return base / "esperimenti" / etichetta, base / PRIVATE_SUBDIR / "esperimenti" / etichetta


def leggi_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(r) for r in path.read_text(encoding="utf-8").splitlines() if r.strip()]


def aggiungi_jsonl(path: Path, riga: dict[str, Any]) -> None:
    """Append e fsync: un'interruzione subito dopo non perde l'esecuzione."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(riga, ensure_ascii=False, default=str) + "\n")
        f.flush()
        os.fsync(f.fileno())


# --- Varianti e manifesto -------------------------------------------------------------------------


def analizza_variante(testo: str) -> dict[str, Any]:
    """`nome:chiave=valore,...` con chiavi `modello` e `semantica` (0/1)."""
    nome, _, resto = testo.partition(":")
    if not nome:
        raise ErroreEsperimento(f"variante senza nome: {testo!r}")
    variante: dict[str, Any] = {
        "nome": nome,
        "modello": agent_config.AGENT_MODEL,
        "semantica": True,
    }
    for coppia in filter(None, resto.split(",")):
        chiave, _, valore = coppia.partition("=")
        if chiave not in CHIAVI_VARIANTE:
            raise ErroreEsperimento(f"chiave sconosciuta {chiave!r} (ammesse: modello, semantica)")
        if chiave == "semantica":
            variante["semantica"] = valore.strip().lower() in ("1", "true", "si", "sì")
        else:
            variante["modello"] = valore.strip()
    return variante


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=app_config.ROOT_DIR, capture_output=True, text=True, check=True
    ).stdout.strip()


def hash_src() -> str:
    """Hash dell'albero `src/` al commit corrente. Rifiuta modifiche non committate in `src/`."""
    if _git("status", "--porcelain", "--", "src"):
        raise ErroreEsperimento(
            "Ci sono modifiche non committate in src/: committale prima di eseguire l'esperimento."
        )
    return _git("rev-parse", "HEAD:src")


def hash_ground_truth(cartella: Path) -> str:
    """sha256 dei file del ground truth (nomi e byte). Il contenuto non viene mai mostrato."""
    h = hashlib.sha256()
    for f in sorted(p for p in cartella.rglob("*") if p.is_file()):
        h.update(f.relative_to(cartella).as_posix().encode())
        h.update(f.read_bytes())
    return h.hexdigest()


def limiti_correnti(timeout: float) -> dict[str, Any]:
    return {
        "agent_max_requests": agent_config.AGENT_MAX_REQUESTS,
        "timeout_lavoro_s": timeout,
        "search_max_distance": agent_config.SEARCH_MAX_DISTANCE,
        "elenco_per_pagina": agent_config.ELENCO_PER_PAGINA,
        "testo_max_k": agent_config.TESTO_MAX_K,
        "sql_max_caratteri": agent_config.SQL_MAX_CARATTERI,
        "sql_righe_anteprima": agent_config.SQL_RIGHE_ANTEPRIMA,
        "sql_righe_lette": agent_config.SQL_RIGHE_LETTE,
        "limiti_rpm_tpm": {k: list(v) for k, v in agent_config.LIMITI.items()},
    }


# Campi che una ripresa deve ritrovare identici (codice, ground truth, limiti).
CAMPI_VERIFICATI = ("src", "ground_truth", "domande", "limiti")


def stato_corrente(gt_dir: Path, domande: list[int], timeout: float) -> dict[str, Any]:
    return {
        "src": hash_src(),
        "ground_truth": hash_ground_truth(gt_dir),
        "domande": domande,
        "limiti": limiti_correnti(timeout),
    }


def crea_manifesto(
    etichetta: str,
    varianti: list[dict[str, Any]],
    ripetizioni: int,
    giudice: str | None,
    criterio: str | None,
    stato: dict[str, Any],
) -> dict[str, Any]:
    nomi = [v["nome"] for v in varianti]
    if len(set(nomi)) != len(nomi):
        raise ErroreEsperimento("nomi di variante duplicati")
    crit = riepilogo.analizza_criterio(criterio) if criterio else None
    if crit and {crit["variante"], crit["riferimento"]} - set(nomi):
        raise ErroreEsperimento("il criterio nomina varianti che non esistono")
    return {
        "etichetta": etichetta,
        "creato_il": datetime.now().astimezone().isoformat(timespec="seconds"),
        "varianti": varianti,
        "ripetizioni": ripetizioni,
        "giudice": giudice,
        "criterio": crit,
        **stato,
    }


def verifica_ripresa(manifesto: dict[str, Any], stato: dict[str, Any]) -> None:
    diversi = [k for k in CAMPI_VERIFICATI if manifesto.get(k) != stato.get(k)]
    if diversi:
        raise ErroreEsperimento(
            "Lo stato attuale non coincide con il manifesto dell'esperimento: "
            f"{', '.join(diversi)}. Torna al codice e al ground truth originali o usa una nuova "
            "etichetta."
        )


# --- Esecuzione -----------------------------------------------------------------------------------

Eseguitore = Callable[[Domanda, dict[str, Any], str | None, float], RisultatoDomanda]


def _esegui_reale(
    d: Domanda, variante: dict[str, Any], giudice: str | None, timeout: float
) -> RisultatoDomanda:
    return esegui_domanda(
        d,
        model=variante["modello"],
        judge=giudice is not None,
        judge_model=giudice,
        timeout=timeout,
        ricerca_semantica=variante["semantica"],
    )


def esegui_esperimento(
    manifesto: dict[str, Any],
    domande: list[Domanda],
    pub: Path,
    priv: Path,
    eseguitore: Eseguitore = _esegui_reale,
    pausa: float = PAUSA_S,
    tentativi_finali: int = TENTATIVI_FINALI,
    dormi: Callable[[float], None] = time.sleep,
    avviso: Callable[[str], None] = print,
) -> None:
    """Esegue le combinazioni non ancora chiuse; poi ritenta quelle rimaste aperte."""
    file_pub, file_priv = pub / "esecuzioni.jsonl", priv / "esecuzioni.jsonl"
    righe = leggi_jsonl(file_pub)
    chiuse = set(riepilogo.esecuzioni_chiuse(righe))
    tentativi: dict[tuple[str, int, int], int] = {}
    for r in righe:
        c = riepilogo.combo(r)
        tentativi[c] = max(tentativi.get(c, 0), r["tentativo"])
    timeout = manifesto["limiti"]["timeout_lavoro_s"]
    per_nome = {v["nome"]: v for v in manifesto["varianti"]}
    ordine = [
        (v["nome"], rip, d)
        for rip in range(1, manifesto["ripetizioni"] + 1)
        for v in manifesto["varianti"]
        for d in domande
    ]
    prima = True

    def una(nome: str, rip: int, d: Domanda) -> None:
        nonlocal prima
        if not prima and pausa:
            dormi(pausa)
        prima = False
        c = (nome, rip, d.id)
        tentativo = tentativi.get(c, 0) + 1
        avviso(f"[{nome} · rip {rip} · #{d.id}] tentativo {tentativo}…")
        r = eseguitore(d, per_nome[nome], manifesto["giudice"], timeout)
        aggiungi_jsonl(file_priv, riga_esecuzione_privata(r, nome, rip, tentativo))
        aggiungi_jsonl(file_pub, riga_esecuzione_pubblica(r, nome, rip, tentativo))
        tentativi[c] = tentativo
        if r.stato in riepilogo.STATI_CHIUSI:
            chiuse.add(c)
        dettaglio = (
            r.esito if r.stato == "completata" else f"{r.stato}: {r.errore or r.errore_giudice}"
        )
        avviso(f"[{nome} · rip {rip} · #{d.id}] {dettaglio} ({r.richieste} richieste)")

    for nome, rip, d in ordine:
        if (nome, rip, d.id) not in chiuse:
            una(nome, rip, d)
    for giro in range(tentativi_finali):
        aperte = [(n, rip, d) for n, rip, d in ordine if (n, rip, d.id) not in chiuse]
        if not aperte:
            break
        avviso(f"Passaggio finale {giro + 1}: {len(aperte)} combinazioni ancora aperte")
        for nome, rip, d in aperte:
            una(nome, rip, d)


# --- Comandi --------------------------------------------------------------------------------------


def _leggi_manifesto(pub: Path) -> dict[str, Any] | None:
    f = pub / "manifest.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def cmd_esegui(args: argparse.Namespace) -> None:
    pub, priv = cartelle(args.etichetta)
    gt = carica(args.gt)
    tutte = {d.id: d for d in gt.domande}
    manifesto = _leggi_manifesto(pub)
    if manifesto is None:
        if not args.variante:
            raise ErroreEsperimento("nuovo esperimento: indica almeno una --variante")
        ids = [int(x) for x in args.ids.split(",")] if args.ids else sorted(tutte)
        timeout = TIMEOUT_DOMANDA_S if args.timeout is None else args.timeout
        stato = stato_corrente(args.gt, ids, timeout)
        giudice = (args.judge_model or agent_config.JUDGE_MODEL) if args.judge else None
        manifesto = crea_manifesto(
            args.etichetta,
            [analizza_variante(v) for v in args.variante],
            args.ripetizioni,
            giudice,
            args.criterio,
            stato,
        )
        pub.mkdir(parents=True, exist_ok=True)
        (pub / "manifest.json").write_text(
            json.dumps(manifesto, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"Nuovo esperimento {args.etichetta}: manifesto in {pub / 'manifest.json'}")
    else:
        if args.variante or args.ids or args.criterio or args.timeout is not None:
            raise ErroreEsperimento(
                "esperimento esistente: la ripresa usa i parametri del manifesto (togli --variante, "
                "--ids, --criterio, --timeout)"
            )
        timeout = manifesto["limiti"]["timeout_lavoro_s"]
        verifica_ripresa(manifesto, stato_corrente(args.gt, manifesto["domande"], timeout))
        print(f"Ripresa di {args.etichetta}")
    mancanti = [i for i in manifesto["domande"] if i not in tutte]
    if mancanti:
        raise ErroreEsperimento(f"domande del manifesto assenti dal ground truth: {mancanti}")
    modelli = [v["modello"] for v in manifesto["varianti"]]
    problemi = controlla_ambiente(
        modelli + ([manifesto["giudice"]] if manifesto["giudice"] else [])
    )
    if problemi:
        raise ErroreEsperimento("Ambiente non pronto:\n- " + "\n- ".join(problemi))
    domande = [tutte[i] for i in manifesto["domande"]]
    try:
        esegui_esperimento(
            manifesto, domande, pub, priv, pausa=args.pausa, tentativi_finali=args.tentativi_finali
        )
    except KeyboardInterrupt:
        print(
            "\nInterrotto: le esecuzioni concluse sono salvate. Rilancia `esegui` per riprendere."
        )
        return
    except ErroreFatale as e:
        print(
            f"\nFermato per {e}: credito esaurito o chiave non valida. Le esecuzioni concluse sono "
            "salvate: ricarica o correggi la chiave e rilancia "
            f"`esegui --etichetta {args.etichetta}`."
        )
        return
    scrivi_riepilogo(args.etichetta)


def scrivi_riepilogo(etichetta: str) -> dict[str, Any]:
    pub, _ = cartelle(etichetta)
    manifesto = _leggi_manifesto(pub)
    if manifesto is None:
        raise ErroreEsperimento(f"esperimento {etichetta!r} inesistente")
    kappa_file = pub / "kappa.json"
    kappa = json.loads(kappa_file.read_text(encoding="utf-8")) if kappa_file.exists() else None
    riep = riepilogo.riepiloga(manifesto, leggi_jsonl(pub / "esecuzioni.jsonl"), kappa)
    (pub / "riepilogo.json").write_text(
        json.dumps(riep, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    md = riepilogo.markdown(manifesto, riep)
    (pub / "riepilogo.md").write_text(md, encoding="utf-8")
    print(md)
    return riep


def main() -> None:
    os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")
    if hasattr(sys.stdout, "reconfigure"):  # console Windows: κ, ≥, − nel riepilogo
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(prog="python -m agentic_rag.eval.esperimento", description=__doc__)
    sub = p.add_subparsers(dest="comando", required=True)

    e = sub.add_parser("esegui", help="crea o riprende un esperimento")
    e.add_argument("--etichetta", required=True)
    e.add_argument("--variante", action="append", help="nome:modello=...,semantica=0|1")
    e.add_argument("--ripetizioni", type=int, default=5)
    e.add_argument("--ids", help="solo queste domande (separate da virgola)")
    e.add_argument("--judge", action="store_true", help="giudice LLM sulla correttezza")
    e.add_argument(
        "--judge-model", help=f"modello del giudice (default {agent_config.JUDGE_MODEL})"
    )
    e.add_argument("--criterio", help="es. task_success_rate:con-senza>=10")
    e.add_argument(
        "--pausa", type=float, default=PAUSA_S, help="secondi tra un'esecuzione e l'altra"
    )
    e.add_argument("--tentativi-finali", type=int, default=TENTATIVI_FINALI)
    e.add_argument(
        "--timeout",
        type=float,
        help=f"secondi di lavoro per domanda (default {TIMEOUT_DOMANDA_S:.0f}; solo alla creazione)",
    )
    e.add_argument("--gt", type=Path, default=GROUND_TRUTH_DIR)

    r = sub.add_parser("riepilogo", help="ricalcola il riepilogo dalle esecuzioni salvate")
    r.add_argument("--etichetta", required=True)

    t = sub.add_parser("etichette", help="foglio privato per l'etichettatura umana (alla cieca)")
    t.add_argument("--etichetta", required=True)
    t.add_argument("--campione", type=int, default=30)

    k = sub.add_parser("kappa", help="accordo tra etichette umane e giudice (kappa di Cohen)")
    k.add_argument("--etichetta", required=True)

    args = p.parse_args()
    try:
        if args.comando == "esegui":
            cmd_esegui(args)
        elif args.comando == "riepilogo":
            scrivi_riepilogo(args.etichetta)
        elif args.comando == "etichette":
            _, priv = cartelle(args.etichetta)
            path, n = etichette.esporta(priv, args.campione)
            print(f"Foglio con {n} risposte in {path} (privato: compilalo tu, non condividerlo)")
        else:
            pub, priv = cartelle(args.etichetta)
            risultato = etichette.calcola_kappa(priv)
            (pub / "kappa.json").write_text(json.dumps(risultato, indent=2), encoding="utf-8")
            print(json.dumps(risultato, indent=2))
            scrivi_riepilogo(args.etichetta)
    except ErroreEsperimento as e:
        raise SystemExit(str(e)) from e


if __name__ == "__main__":
    main()
