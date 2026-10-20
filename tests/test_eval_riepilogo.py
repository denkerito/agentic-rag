import pytest

from agentic_rag.eval.riepilogo import (
    analizza_criterio,
    appaiate,
    efficienza,
    esecuzioni_chiuse,
    markdown,
    riepiloga,
    validita,
)


def _riga(variante: str, rip: int, id_: int, esito: str = "ok", stato: str = "completata", **c):
    conteggi = {
        "fonti_attese": 2,
        "fonti_trovate": 2,
        "numeri_attesi": None,
        "numeri_trovati": None,
        "documenti_attesi": 1,
        "documenti_recuperati": 1,
        "causa_attesa": None,
        "causa_dichiarata_documentata": False,
        "giudice": "corretta",
        "citate_non_viste": 0,
    } | c
    return {
        "variante": variante,
        "ripetizione": rip,
        "id": id_,
        "tentativo": 1,
        "stato": stato,
        "esito": esito if stato == "completata" else "errore",
        "modalita": "normale",
        "richieste": 8,
        "passi_tool": 6,
        "token_input": 1000,
        "token_output": 100,
        "attesa_s": 0.0,
        "lavoro_s": 30.0,
        "rifiuti": {},
        "conteggi": conteggi,
    }


def _manifesto(varianti=("con", "senza"), ripetizioni=1, domande=(1, 2), criterio=None):
    return {
        "etichetta": "esp",
        "creato_il": "2026-10-19",
        "src": "abcdef1234567",
        "giudice": "google:m",
        "ripetizioni": ripetizioni,
        "domande": list(domande),
        "varianti": [{"nome": v, "modello": "google:m", "semantica": v == "con"} for v in varianti],
        "criterio": criterio,
    }


def test_l_ultima_esecuzione_chiusa_chiude_la_combinazione() -> None:
    righe = [
        _riga("con", 1, 1, stato="errore_infrastruttura"),
        _riga("con", 1, 1, esito="ko"),
    ]
    chiuse = esecuzioni_chiuse(righe)
    assert list(chiuse) == [("con", 1, 1)] and chiuse[("con", 1, 1)]["esito"] == "ko"


def test_validita_oltre_il_10_per_cento_di_escluse() -> None:
    m = _manifesto(domande=range(1, 11))
    righe = [_riga(v, 1, i) for v in ("con", "senza") for i in range(1, 11)]
    assert validita(m, esecuzioni_chiuse(righe))[0]
    meno_due = [r for r in righe if not (r["variante"] == "senza" and r["id"] in (1, 2))]
    valido, dettaglio = validita(m, esecuzioni_chiuse(meno_due))
    assert not valido and dettaglio["escluse"]["senza"] == [[1, 1], [1, 2]]
    assert any("senza" in x for x in dettaglio["motivi_invalidita"])


def test_confronto_appaiato_toglie_le_combinazioni_mancanti_in_una_variante() -> None:
    righe = [_riga("con", 1, 1), _riga("con", 1, 2), _riga("senza", 1, 1)]
    a, b = appaiate(esecuzioni_chiuse(righe), "con", "senza")
    assert [r["id"] for r in a] == [1] and [r["id"] for r in b] == [1]


def test_criterio() -> None:
    assert analizza_criterio("task_success_rate:con-senza>=10") == {
        "metrica": "task_success_rate",
        "variante": "con",
        "riferimento": "senza",
        "soglia": 10.0,
    }
    with pytest.raises(ValueError):
        analizza_criterio("metrica_inventata:a-b>=1")


def test_riepilogo_metriche_verdetto_e_markdown() -> None:
    crit = analizza_criterio("task_success_rate:con-senza>=10")
    m = _manifesto(ripetizioni=3, criterio=crit)
    righe = []
    for rip in (1, 2, 3):
        righe += [_riga("con", rip, 1), _riga("con", rip, 2)]
        righe += [_riga("senza", rip, 1), _riga("senza", rip, 2, esito="ko")]
    # una domanda onesta in cui la variante "senza" inventa la causa
    righe[3]["conteggi"] |= {
        "causa_attesa": "non_documentata",
        "causa_dichiarata_documentata": True,
    }
    riep = riepiloga(m, righe)
    con, senza = riep["varianti"]["con"]["metriche"], riep["varianti"]["senza"]["metriche"]
    assert con["task_success_rate"]["valore"] == 1.0 and senza["task_success_rate"]["valore"] == 0.5
    assert senza["false_acceptance_rate"]["esecuzioni"] == 1
    assert con["false_acceptance_rate"]["valore"] is None  # non applicabile: denominatore 0
    assert con["pass_hat_3"]["valore"] == 1.0 and senza["pass_hat_3"]["valore"] == 0.5
    assert riep["verdetto"]["esito"] == "supera" and riep["verdetto"]["differenza_punti"] == 50.0
    testo = markdown(m, riep)
    assert "Task Success Rate" in testo and "supera" in testo


def test_esperimento_non_valido_non_da_verdetto() -> None:
    crit = analizza_criterio("task_success_rate:con-senza>=10")
    m = _manifesto(domande=(1, 2), criterio=crit)
    righe = [_riga("con", 1, 1), _riga("con", 1, 2), _riga("senza", 1, 1)]
    riep = riepiloga(m, righe)
    assert not riep["valido"] and riep["verdetto"]["esito"] == "non valutato"


def test_fallita_agente_conta_nel_task_success_e_nei_rifiuti() -> None:
    m = _manifesto(varianti=("con",), domande=(1,), ripetizioni=2)
    fallita = _riga("con", 2, 1, stato="fallita_agente")
    fallita["rifiuti"] = {"fonti_non_viste": 4}  # il validatore ha rifiutato fino al fallimento
    riep = riepiloga(m, [_riga("con", 1, 1), fallita])["varianti"]["con"]
    met = riep["metriche"]
    assert met["task_success_rate"]["valore"] == 0.5
    assert met["answer_accuracy"]["valore"] == 1.0 and met["answer_accuracy"]["esecuzioni"] == 1
    gir = met["guardrail_intervention_rate"]
    assert gir["valore"] == 0.5 and gir["esecuzioni"] == 2
    assert riep["rifiuti_per_motivo"] == {"fonti_non_viste": 4}


def test_efficienza_righe_senza_tentativi_provider() -> None:
    # righe salvate prima di questo campo: il riepilogo non si rompe e conta 0
    e = efficienza([_riga("con", 1, 1)], None)
    assert e["tentativi_provider_medi"] == 0 and "attesa_media_s" in e


def test_efficienza_media_dei_tentativi_provider() -> None:
    righe = [
        _riga("con", 1, 1) | {"tentativi_provider": 2},
        _riga("con", 1, 2) | {"tentativi_provider": 0},
    ]
    assert efficienza(righe, None)["tentativi_provider_medi"] == 1.0
