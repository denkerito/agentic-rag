"""Riepilogo di un esperimento dalle righe pubbliche: metriche, intervalli, confronti, validità.

Le definizioni (nomi, denominatori, salvaguardie) sono nel documento di design dell'harness:
docs/superpowers/specs/2026-10-19-harness-esperimenti-design.md.
"""

import re
from collections import defaultdict
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any

from agentic_rag.eval.statistica import Stima, bootstrap, bootstrap_appaiato, pass_hat_k, percentile

Riga = dict[str, Any]
Combo = tuple[str, int, int]  # (variante, ripetizione, id domanda)

STATI_CHIUSI = ("completata", "fallita_agente")
K_PASS = 3
SOGLIA_ESCLUSE = 0.10  # oltre il 10% di combinazioni escluse la variante invalida l'esperimento
SOGLIA_SBILANCIAMENTO = 0.05  # differenza massima tra varianti nella quota di escluse
# Prezzi in USD per milione di token (ingresso, uscita), per nome di modello. Vuota finché non si
# sceglie il modello: senza prezzo il costo è n/d.
PREZZI: dict[str, tuple[float, float]] = {}


def combo(r: Riga) -> Combo:
    return (r["variante"], r["ripetizione"], r["id"])


def esecuzioni_chiuse(righe: list[Riga]) -> dict[Combo, Riga]:
    """Per ogni combinazione, l'esecuzione che la chiude (completata o fallita per l'agente)."""
    out: dict[Combo, Riga] = {}
    for r in righe:
        if r["stato"] in STATI_CHIUSI:
            out[combo(r)] = r
    return out


# --- Metriche: per ogni esecuzione un valore (None = non applicabile) -----------------------------


def _completata(r: Riga) -> bool:
    return r["stato"] == "completata"


def _frazione(num: Any, den: Any) -> float | None:
    return num / den if den and num is not None else None


def m_task_success(r: Riga) -> float:
    return float(r["esito"] == "ok")


def m_answer_accuracy(r: Riga) -> float | None:
    g = r["conteggi"]["giudice"] if _completata(r) else None
    return None if g is None else float(g == "corretta")


def m_answer_partial(r: Riga) -> float | None:
    g = r["conteggi"]["giudice"] if _completata(r) else None
    return None if g is None else float(g == "parziale")


def m_citation_recall(r: Riga) -> float | None:
    c = r["conteggi"]
    return _frazione(c["fonti_trovate"], c["fonti_attese"]) if _completata(r) else None


def m_numeric_recall(r: Riga) -> float | None:
    c = r["conteggi"]
    return _frazione(c["numeri_trovati"], c["numeri_attesi"]) if _completata(r) else None


def m_false_acceptance(r: Riga) -> float | None:
    c = r["conteggi"]
    if not _completata(r) or c["causa_attesa"] != "non_documentata":
        return None
    return float(bool(c["causa_dichiarata_documentata"]))


def m_false_abstention(r: Riga) -> float | None:
    c = r["conteggi"]
    if not _completata(r) or c["causa_attesa"] != "documentata":
        return None
    return float(not c["causa_dichiarata_documentata"])


def m_guardrail(r: Riga) -> float | None:
    return float(sum(r["rifiuti"].values()) > 0) if _completata(r) else None


def m_evidence_recall(r: Riga) -> float | None:
    c = r["conteggi"]
    return _frazione(c["documenti_recuperati"], c["documenti_attesi"]) if _completata(r) else None


@dataclass(frozen=True)
class Metrica:
    chiave: str
    nome: str
    funzione: Callable[[Riga], float | None]
    alto_e_meglio: bool = True


METRICHE: list[Metrica] = [
    Metrica("task_success_rate", "Task Success Rate", m_task_success),
    Metrica("answer_accuracy", "Answer Accuracy (LLM-as-a-judge)", m_answer_accuracy),
    Metrica("answer_partial", "  di cui parziali", m_answer_partial, alto_e_meglio=False),
    Metrica("source_citation_recall", "Source Citation Recall", m_citation_recall),
    Metrica("numeric_exact_match_recall", "Numeric Exact Match Recall", m_numeric_recall),
    Metrica("false_acceptance_rate", "False Acceptance Rate", m_false_acceptance, False),
    Metrica("false_abstention_rate", "False Abstention Rate", m_false_abstention, False),
    Metrica("guardrail_intervention_rate", "Guardrail Intervention Rate", m_guardrail, False),
    Metrica("session_evidence_recall", "Session Evidence Recall", m_evidence_recall),
]
METRICHE_PER_CHIAVE = {m.chiave: m for m in METRICHE}


def per_domanda(righe: list[Riga], f: Callable[[Riga], float | None]) -> dict[int, float]:
    """Media della metrica sulle esecuzioni di ogni domanda (solo dove si applica)."""
    valori: dict[int, list[float]] = defaultdict(list)
    for r in righe:
        x = f(r)
        if x is not None:
            valori[r["id"]].append(x)
    return {k: sum(v) / len(v) for k, v in valori.items()}


def stima(righe: list[Riga], f: Callable[[Riga], float | None]) -> tuple[Stima, int]:
    """Stima con intervallo e numero di esecuzioni su cui si applica."""
    n = sum(f(r) is not None for r in righe)
    return bootstrap(list(per_domanda(righe, f).values())), n


def pass_k(righe: list[Riga], k: int = K_PASS) -> tuple[Stima, int]:
    """pass^k medio sulle domande con almeno k esecuzioni chiuse; restituisce anche le escluse."""
    per_id: dict[int, list[bool]] = defaultdict(list)
    for r in righe:
        per_id[r["id"]].append(r["esito"] == "ok")
    valori = [pass_hat_k(len(v), sum(v), k) for v in per_id.values() if len(v) >= k]
    return bootstrap(valori), sum(len(v) < k for v in per_id.values())


def efficienza(righe: list[Riga], modello: str | None) -> dict[str, Any]:
    if not righe:
        return {}
    n = len(righe)
    tin = sum(r["token_input"] for r in righe) / n
    tout = sum(r["token_output"] for r in righe) / n
    prezzo = PREZZI.get(modello or "")
    lavoro = [r["lavoro_s"] for r in righe]
    return {
        "esecuzioni": n,
        "token_input_medi": round(tin),
        "token_output_medi": round(tout),
        "richieste_medie": round(sum(r["richieste"] for r in righe) / n, 1),
        "chiamate_tool_medie": round(sum(r["passi_tool"] for r in righe) / n, 1),
        "lavoro_p50_s": percentile(lavoro, 0.5),
        "lavoro_p95_s": percentile(lavoro, 0.95),
        "attesa_limitatore_media_s": round(sum(r["attesa_s"] for r in righe) / n, 1),
        "costo_medio_usd": (tin * prezzo[0] + tout * prezzo[1]) / 1e6 if prezzo else None,
    }


def rifiuti_per_motivo(righe: list[Riga]) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for r in righe:
        for motivo, n in r["rifiuti"].items():
            out[motivo] += n
    return dict(out)


# --- Validità, confronti, criterio ----------------------------------------------------------------


def validita(manifesto: dict[str, Any], chiuse: dict[Combo, Riga]) -> tuple[bool, dict[str, Any]]:
    varianti = [v["nome"] for v in manifesto["varianti"]]
    domande = manifesto["domande"]
    ripetizioni = manifesto["ripetizioni"]
    totale = ripetizioni * len(domande)
    escluse: dict[str, list[Combo]] = {}
    for v in varianti:
        escluse[v] = [
            (v, rip, d)
            for rip in range(1, ripetizioni + 1)
            for d in domande
            if (v, rip, d) not in chiuse
        ]
    quote = {v: len(e) / totale if totale else 0.0 for v, e in escluse.items()}
    motivi = [
        f"{v}: {q:.0%} di combinazioni escluse" for v, q in quote.items() if q > SOGLIA_ESCLUSE
    ]
    if quote and max(quote.values()) - min(quote.values()) > SOGLIA_SBILANCIAMENTO:
        motivi.append("combinazioni escluse sbilanciate tra le varianti")
    dettaglio = {
        "combinazioni_per_variante": totale,
        "escluse": {v: [list(c[1:]) for c in e] for v, e in escluse.items()},
        "quote_escluse": quote,
        "motivi_invalidita": motivi,
    }
    return not motivi, dettaglio


def appaiate(chiuse: dict[Combo, Riga], a: str, b: str) -> tuple[list[Riga], list[Riga]]:
    """Esecuzioni di a e b sulle sole (ripetizione, domanda) chiuse in entrambe."""
    ka = {(c[1], c[2]) for c in chiuse if c[0] == a}
    kb = {(c[1], c[2]) for c in chiuse if c[0] == b}
    comuni = sorted(ka & kb)
    return [chiuse[(a, *k)] for k in comuni], [chiuse[(b, *k)] for k in comuni]


CRITERIO_RE = re.compile(r"^(?P<m>[a-z_]+):(?P<a>[\w.-]+)-(?P<b>[\w.-]+)>=(?P<s>-?\d+(\.\d+)?)$")


def analizza_criterio(testo: str) -> dict[str, Any]:
    """`metrica:variante-riferimento>=punti`, es. `task_success_rate:con-senza>=10`."""
    m = CRITERIO_RE.match(testo.replace(" ", ""))
    if not m or m["m"] not in METRICHE_PER_CHIAVE:
        raise ValueError(f"criterio non valido: {testo!r}")
    return {"metrica": m["m"], "variante": m["a"], "riferimento": m["b"], "soglia": float(m["s"])}


def differenza(
    chiuse: dict[Combo, Riga], a: str, b: str, f: Callable[[Riga], float | None]
) -> Stima:
    ra, rb = appaiate(chiuse, a, b)
    return bootstrap_appaiato(per_domanda(ra, f), per_domanda(rb, f))


def verdetto(criterio: dict[str, Any], chiuse: dict[Combo, Riga], valido: bool) -> dict[str, Any]:
    if not valido:
        return {"esito": "non valutato", "motivo": "esperimento non valido"}
    metrica = METRICHE_PER_CHIAVE[criterio["metrica"]]
    d = differenza(chiuse, criterio["variante"], criterio["riferimento"], metrica.funzione)
    if d.valore is None:
        return {"esito": "non valutato", "motivo": "nessuna domanda in comune"}
    punti = 100 * d.valore
    supera = punti >= criterio["soglia"]
    return {
        "esito": "supera" if supera else "non supera",
        "differenza_punti": round(punti, 1),
        "intervallo_punti": [round(100 * d.basso, 1), round(100 * d.alto, 1)],  # type: ignore[operator]
        "soglia": criterio["soglia"],
    }


# --- Riepilogo completo ---------------------------------------------------------------------------


def _stima_json(s: Stima, n: int) -> dict[str, Any]:
    return asdict(s) | {"esecuzioni": n}


def riepiloga(manifesto: dict[str, Any], righe: list[Riga], kappa: dict | None = None) -> dict:
    chiuse = esecuzioni_chiuse(righe)
    valido, dettaglio_validita = validita(manifesto, chiuse)
    varianti = manifesto["varianti"]
    out: dict[str, Any] = {
        "etichetta": manifesto["etichetta"],
        "valido": valido,
        "validita": dettaglio_validita,
        "varianti": {},
        "confronti": {},
        "kappa": kappa,
    }
    errori_infra: dict[str, int] = defaultdict(int)
    for r in righe:
        if r["stato"] == "errore_infrastruttura":
            errori_infra[r["variante"]] += 1
    for v in varianti:
        nome = v["nome"]
        rv = [r for c, r in chiuse.items() if c[0] == nome]
        metriche = {m.chiave: _stima_json(*stima(rv, m.funzione)) for m in METRICHE}
        pk, escluse_pk = pass_k(rv)
        metriche[f"pass_hat_{K_PASS}"] = asdict(pk) | {"domande_escluse": escluse_pk}
        per_modalita: dict[str, Any] = {}
        for modalita in sorted({r["modalita"] for r in rv}):
            rm = [r for r in rv if r["modalita"] == modalita]
            per_modalita[modalita] = {
                m.chiave: _stima_json(*stima(rm, m.funzione)) for m in METRICHE
            }
        out["varianti"][nome] = {
            "config": v,
            "chiuse": len(rv),
            "fallite_agente": sum(r["stato"] == "fallita_agente" for r in rv),
            "errori_infrastruttura": errori_infra[nome],
            "metriche": metriche,
            "per_modalita": per_modalita,
            "rifiuti_per_motivo": rifiuti_per_motivo(rv),
            "efficienza": efficienza(rv, v.get("modello")),
        }
    riferimento = varianti[0]["nome"]
    for v in varianti[1:]:
        out["confronti"][f"{v['nome']} - {riferimento}"] = {
            m.chiave: asdict(differenza(chiuse, v["nome"], riferimento, m.funzione))
            for m in METRICHE
        }
    if manifesto.get("criterio"):
        out["verdetto"] = verdetto(manifesto["criterio"], chiuse, valido)
    return out


# --- Markdown -------------------------------------------------------------------------------------


def _pct(s: dict[str, Any]) -> str:
    if s["valore"] is None:
        return "n/a"
    return f"{100 * s['valore']:.1f}% [{100 * s['basso']:.1f}, {100 * s['alto']:.1f}]"


def markdown(manifesto: dict[str, Any], riep: dict[str, Any]) -> str:
    nomi = list(riep["varianti"])
    out = [f"# Esperimento {riep['etichetta']}", ""]
    out.append(f"- creato: {manifesto['creato_il']} · codice `src` {manifesto['src'][:10]}")
    out.append(f"- ripetizioni: {manifesto['ripetizioni']} · domande: {len(manifesto['domande'])}")
    out.append(f"- giudice: {manifesto['giudice'] or 'spento'}")
    for v in manifesto["varianti"]:
        out.append(f"- variante `{v['nome']}`: modello {v['modello']}, semantica {v['semantica']}")
    stato = (
        "**valido**"
        if riep["valido"]
        else "**NON valido**: " + "; ".join(riep["validita"]["motivi_invalidita"])
    )
    out += ["", f"Esperimento {stato}.", ""]
    if "verdetto" in riep:
        c = manifesto["criterio"]
        vd = riep["verdetto"]
        out.append(
            f"**Criterio** `{c['metrica']}: {c['variante']} − {c['riferimento']} ≥ "
            f"{c['soglia']:g} punti` → **{vd['esito']}**"
            + (
                f" ({vd['differenza_punti']:+.1f} punti, IC 95% {vd['intervallo_punti']})"
                if "differenza_punti" in vd
                else f" ({vd.get('motivo', '')})"
            )
        )
        out.append("")
    out += ["## Metriche (media sulle domande, IC 95% bootstrap)", ""]
    out.append("| Metrica | " + " | ".join(nomi) + " |")
    out.append("|---|" + "---|" * len(nomi))
    for m in METRICHE:
        celle = []
        for n in nomi:
            s = riep["varianti"][n]["metriche"][m.chiave]
            celle.append(f"{_pct(s)} · n={s['esecuzioni']}")
        out.append(f"| {m.nome} | " + " | ".join(celle) + " |")
    celle = []
    for n in nomi:
        s = riep["varianti"][n]["metriche"][f"pass_hat_{K_PASS}"]
        celle.append(f"{_pct(s)} · domande={s['domande']}")
    out.append(f"| pass^{K_PASS} | " + " | ".join(celle) + " |")
    out += ["", "## Efficienza", ""]
    chiavi = list(next(iter(riep["varianti"].values()))["efficienza"]) if nomi else []
    out.append("| | " + " | ".join(nomi) + " |")
    out.append("|---|" + "---|" * len(nomi))
    for k in chiavi:
        valori = [riep["varianti"][n]["efficienza"].get(k) for n in nomi]
        out.append(
            f"| {k} | "
            + " | ".join(
                "n/d" if x is None else (f"{x:.1f}" if isinstance(x, float) else str(x))
                for x in valori
            )
            + " |"
        )
    out += ["", "## Esecuzioni", ""]
    for n in nomi:
        v = riep["varianti"][n]
        out.append(
            f"- `{n}`: {v['chiuse']} chiuse ({v['fallite_agente']} fallite per l'agente), "
            f"{v['errori_infrastruttura']} errori di infrastruttura registrati, "
            f"rifiuti del validatore {v['rifiuti_per_motivo'] or 'nessuno'}"
        )
    escluse = riep["validita"]["escluse"]
    if any(escluse.values()):
        out.append("")
        out.append("Combinazioni escluse (ripetizione, domanda):")
        for n, e in escluse.items():
            if e:
                out.append(f"- `{n}`: {e}")
    if riep["confronti"]:
        out += ["", "## Confronti appaiati (differenza in punti, IC 95%)", ""]
        nomi_c = list(riep["confronti"])
        out.append("| Metrica | " + " | ".join(nomi_c) + " |")
        out.append("|---|" + "---|" * len(nomi_c))
        for m in METRICHE:
            celle = []
            for c in nomi_c:
                s = riep["confronti"][c][m.chiave]
                celle.append(
                    "n/a"
                    if s["valore"] is None
                    else f"{100 * s['valore']:+.1f} [{100 * s['basso']:+.1f}, {100 * s['alto']:+.1f}]"
                )
            out.append(f"| {m.nome} | " + " | ".join(celle) + " |")
    if riep.get("kappa"):
        k = riep["kappa"]
        out += [
            "",
            "## Validazione del giudice",
            "",
            (
                f"Campione di {k['campione']} risposte etichettate a mano: κ di Cohen "
                f"{k['kappa_3_classi']} (3 classi), {k['kappa_binario']} (corretta/non corretta), "
                f"accordo {k['accordo']:.0%}."
            ),
        ]
    out += [
        "",
        (
            "Note: le metriche sulla risposta si calcolano sulle esecuzioni completate; il Task "
            "Success Rate conta anche quelle fallite per l'agente. Le attese dei tentativi interni "
            "del client del provider (429/5xx) restano nella latenza."
        ),
    ]
    return "\n".join(out) + "\n"
