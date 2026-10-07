"""Report: uno PUBBLICO (si può condividere) e uno PRIVATO (contiene il ground truth).

Il pubblico contiene solo: id della domanda, storia, modalità, esito, conteggi (es. "2/3"), la
risposta e le query dell'AGENTE. Mai la domanda, il `tipo` originale, la risposta attesa, gli ID
attesi o i numeri attesi: quelli stanno solo nel privato.
"""

import json
from collections import defaultdict
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from agentic_rag import config
from agentic_rag.eval.runner import RisultatoDomanda

REPORTS_DIR: Path = config.ROOT_DIR / "eval" / "reports"
PRIVATE_SUBDIR = "private"


def _frazione(trovati: int, attesi: int) -> str | None:
    return f"{trovati}/{attesi}" if attesi else None


def riga_pubblica(r: RisultatoDomanda) -> dict[str, Any]:
    d = r.domanda
    out: dict[str, Any] = {
        "id": d.id,
        "storia": d.storia_chiave or "-",
        "modalita": d.modalita.value,
        "esito": r.esito,
        "richieste": r.richieste,
        "durata_s": round(r.durata_s, 1),
        "sql_agente": r.sql_agente,
        "tabelle_lette": r.tabelle_lette,
    }
    if r.errore:
        out["errore"] = r.errore
    if r.errore_giudice:
        out["errore_giudice"] = r.errore_giudice
    if r.risposta:
        out["risposta"] = {
            "conclusione": r.risposta.conclusione,
            "confidenza": r.risposta.confidenza,
            "causa_documentata": r.risposta.causa_documentata,
            "limiti": r.risposta.limiti,
            "numeri": [n.model_dump() for n in r.risposta.numeri],
            "fonti": r.risposta.fonti,
        }
    v = r.valutazione
    if v:
        out["metriche"] = {
            "fonti_id": _frazione(v.fonti.id_trovati, v.fonti.id_attesi),
            "tabelle": _frazione(v.fonti.tabelle_trovate, v.fonti.tabelle_attese),
            "numeri": _frazione(v.numeri.trovati, v.numeri.attesi)
            if v.numeri.applicabile
            else None,
            "numeri_na": v.numeri.motivo_na,
            "fonti_extra": v.fonti.id_extra,
            "citate_non_viste": v.fonti.citate_non_viste,
            "comportamento_ok": v.comportamento.ok if v.comportamento else None,
            "giudice": v.giudizio.verdetto if v.giudizio else None,
        }
    return out


def riga_privata(r: RisultatoDomanda) -> dict[str, Any]:
    d = r.domanda
    out = riga_pubblica(r)
    out |= {
        "domanda": d.domanda,
        "tipo": d.tipo,
        "storia_id": d.storia_id,
        "risposta_attesa": d.risposta_attesa,
        "fonti_attese": d.fonti_attese,
        "fonti_non_riconosciute": d.fonti_non_riconosciute,
    }
    v = r.valutazione
    if v:
        out["dettaglio"] = {
            "id_mancanti": v.fonti.id_mancanti,
            "tabelle_mancanti": v.fonti.tabelle_mancanti,
            "numeri_attesi": v.numeri.attesi_valori,
            "numeri_mancanti": v.numeri.mancanti,
            "comportamento": v.comportamento.motivo if v.comportamento else None,
            "motivazione_giudice": v.giudizio.motivazione if v.giudizio else None,
        }
    return out


def aggregati(risultati: list[RisultatoDomanda]) -> dict[str, Any]:
    def conta(gruppo: list[RisultatoDomanda]) -> dict[str, Any]:
        esiti = [r.esito for r in gruppo]
        con_modello = [r for r in gruppo if r.richieste]
        return {
            "domande": len(gruppo),
            "ok": esiti.count("ok"),
            "ko": esiti.count("ko"),
            "errore": esiti.count("errore"),
            "nd": esiti.count("nd"),
            "richieste_medie": round(sum(r.richieste for r in con_modello) / len(con_modello), 1)
            if con_modello
            else None,
        }

    per_storia: dict[str, list[RisultatoDomanda]] = defaultdict(list)
    per_modalita: dict[str, list[RisultatoDomanda]] = defaultdict(list)
    for r in risultati:
        per_storia[r.domanda.storia_chiave or "-"].append(r)
        per_modalita[r.domanda.modalita.value].append(r)
    return {
        "totale": conta(risultati),
        "per_storia": {k: conta(v) for k, v in sorted(per_storia.items())},
        "per_modalita": {k: conta(v) for k, v in sorted(per_modalita.items())},
    }


def _md_aggregati(agg: dict[str, Any]) -> list[str]:
    righe = [
        "| Gruppo | Domande | ok | ko | errore | n/d | Richieste medie |",
        "|---|---|---|---|---|---|---|",
    ]
    voci = [("**Totale**", agg["totale"])]
    voci += [(f"storia {k}", v) for k, v in agg["per_storia"].items()]
    voci += [(f"modalità {k}", v) for k, v in agg["per_modalita"].items()]
    for nome, c in voci:
        righe.append(
            f"| {nome} | {c['domande']} | {c['ok']} | {c['ko']} | {c['errore']} | {c['nd']} | "
            f"{c['richieste_medie'] if c['richieste_medie'] is not None else '-'} |"
        )
    return righe


def markdown(
    titolo: str, meta: dict[str, Any], righe: list[dict[str, Any]], agg: dict[str, Any]
) -> str:
    out = [f"# {titolo}", ""]
    out += [f"- {k}: {v}" for k, v in meta.items()]
    out += ["", "## Riepilogo", ""] + _md_aggregati(agg) + ["", "## Domande", ""]
    for r in righe:
        out.append(
            f"### Domanda {r['id']} · storia {r['storia']} · {r['modalita']} · **{r['esito']}**"
        )
        if "domanda" in r:  # solo privato
            out += ["", f"> {r['domanda']}", "", f"Tipo: {r['tipo']}"]
        m = r.get("metriche")
        if m:
            out.append("")
            out.append(
                f"fonti ID {m['fonti_id'] or 'n/a'} · tabelle {m['tabelle'] or 'n/a'} · "
                f"numeri {m['numeri'] or ('n/a: ' + str(m['numeri_na']))} · extra {m['fonti_extra']} · "
                f"citate non viste {m['citate_non_viste']} · comportamento {m['comportamento_ok']} · "
                f"giudice {m['giudice'] or '-'}"
            )
        out.append(f"richieste {r['richieste']} · {r['durata_s']} s")
        if r.get("errore"):
            out.append(f"\n**Errore:** {r['errore']}")
        if r.get("risposta"):
            ris = r["risposta"]
            out += [
                "",
                f"**Agente** (confidenza {ris['confidenza']}, causa documentata {ris['causa_documentata']}):",
                "",
                ris["conclusione"],
            ]
            if ris["limiti"]:
                out += ["", f"_Limiti:_ {ris['limiti']}"]
        if r["sql_agente"]:
            out += ["", "<details><summary>SQL dell'agente</summary>", ""]
            out += [f"```sql\n{s}\n```" for s in r["sql_agente"]] + ["", "</details>"]
        if "risposta_attesa" in r:
            out += [
                "",
                f"**Risposta attesa:** {r['risposta_attesa']}",
                "",
                f"Fonti attese: {r['fonti_attese']}",
            ]
            dett = r.get("dettaglio")
            if dett:
                out += ["", "```json", json.dumps(dett, ensure_ascii=False, indent=2), "```"]
        out.append("")
    return "\n".join(out)


def _serializza(o: Any) -> Any:
    return asdict(o) if is_dataclass(o) and not isinstance(o, type) else str(o)


def scrivi(
    risultati: list[RisultatoDomanda],
    meta: dict[str, Any],
    out_dir: Path = REPORTS_DIR,
    adesso: datetime | None = None,
) -> tuple[dict[str, Path], list[str]]:
    """Scrive pubblico e privato. Ritorna (percorsi, righe da stampare in console: solo pubblico)."""
    ts = (adesso or datetime.now().astimezone()).strftime("%Y%m%d-%H%M%S")
    agg = aggregati(risultati)
    pub = [riga_pubblica(r) for r in risultati]
    priv = [riga_privata(r) for r in risultati]
    privata_dir = out_dir / PRIVATE_SUBDIR
    out_dir.mkdir(parents=True, exist_ok=True)
    privata_dir.mkdir(parents=True, exist_ok=True)
    percorsi = {
        "pubblico_json": out_dir / f"{ts}.json",
        "pubblico_md": out_dir / f"{ts}.md",
        "privato_json": privata_dir / f"{ts}.json",
        "privato_md": privata_dir / f"{ts}.md",
    }
    for chiave, righe in (("pubblico", pub), ("privato", priv)):
        corpo = {"meta": meta, "aggregati": agg, "domande": righe}
        percorsi[f"{chiave}_json"].write_text(
            json.dumps(corpo, ensure_ascii=False, indent=2, default=_serializza), encoding="utf-8"
        )
        percorsi[f"{chiave}_md"].write_text(
            markdown(f"Eval ({chiave})", meta, righe, agg), encoding="utf-8"
        )
    return percorsi, console(pub, agg)


def console(righe_pubbliche: list[dict[str, Any]], agg: dict[str, Any]) -> list[str]:
    """Riepilogo per il terminale: solo dati del report pubblico."""
    out = []
    for r in righe_pubbliche:
        m = r.get("metriche") or {}
        out.append(
            f"#{r['id']:>2} {r['storia']:<6} {r['modalita']:<17} {r['esito']:<6} "
            f"fonti {m.get('fonti_id') or '-':<5} tab {m.get('tabelle') or '-':<5} "
            f"num {m.get('numeri') or '-':<5} req {r['richieste']}"
        )
    t = agg["totale"]
    out.append(
        f"Totale: {t['ok']} ok, {t['ko']} ko, {t['errore']} errori, {t['nd']} n/d su {t['domande']}"
    )
    return out
