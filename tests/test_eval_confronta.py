import json

import pytest

from agentic_rag.eval.confronta import (
    GIUDICE_MANCANTE,
    carica,
    controlla_omogenei,
    riepiloga,
    righe,
    verdetto,
)


def _report(semantica: bool, esiti: list[str], **meta) -> dict:
    domande = [
        {"id": i + 1, "esito": e, "richieste": 8, "durata_s": 30.0} for i, e in enumerate(esiti)
    ]
    base = {
        "data": "2026-10-16",
        "modello": "google:m",
        "giudice": "google:m",
        "ricerca_semantica": semantica,
        "etichetta": "esp",
        "interrotta": False,
    }
    return {"meta": {**base, **meta}, "aggregati": {}, "domande": domande}


def _scrivi(cartella, nome: str, corpo: dict) -> None:
    (cartella / nome).write_text(json.dumps(corpo), encoding="utf-8")


def test_carica_filtra_per_etichetta_e_ignora_privati_e_interrotti(tmp_path) -> None:
    _scrivi(tmp_path, "a.json", _report(True, ["ok"]))
    _scrivi(tmp_path, "b.json", _report(True, ["ok"], etichetta="altro"))
    _scrivi(tmp_path, "c.json", _report(False, ["ok"], interrotta=True))
    (tmp_path / "private").mkdir()
    _scrivi(tmp_path / "private", "a.json", _report(False, ["ok"]))
    assert [r["meta"]["etichetta"] for r in carica(tmp_path, "esp")] == ["esp"]


def test_rifiuta_report_con_modelli_diversi() -> None:
    with pytest.raises(ValueError, match="modello"):
        controlla_omogenei([_report(True, ["ok"]), _report(False, ["ok"], modello="google:x")])


def test_conteggi_per_variante_e_per_domanda() -> None:
    report = [
        _report(True, ["ok", "ko"]),
        _report(True, ["ok", "ok"]),
        _report(False, ["ko", "errore"]),
    ]
    v = riepiloga(report)
    assert v[True].esecuzioni == 4 and v[True].ok_pct == 75.0
    assert v[True].ok_per_domanda[1] == [True, True] and v[True].ok_per_domanda[2] == [False, True]
    assert v[False].esiti["errore"] == 1 and v[False].richieste == [8]  # errori fuori dalle medie


def test_giudice_fallito_non_conta_come_ok() -> None:
    r = _report(True, ["ok"])
    r["domande"][0]["errore_giudice"] = "ModelHTTPError"
    v = riepiloga([r])
    assert v[True].esiti == {GIUDICE_MANCANTE: 1} and v[True].ok_pct == 0.0


def test_verdetto_secondo_la_soglia() -> None:
    dieci = ["ok"] * 6 + ["ko"] * 4
    assert "RESTA" in verdetto(
        riepiloga([_report(True, dieci), _report(False, dieci[1:] + ["ko"])])
    )
    assert "NON supera" in verdetto(
        riepiloga([_report(True, dieci), _report(False, ["ok"] * 6 + ["ko"] * 4)])
    )
    assert "servono entrambe" in verdetto(riepiloga([_report(True, dieci)]))


def test_righe_mostrano_le_due_varianti() -> None:
    testo = "\n".join(righe(riepiloga([_report(True, ["ok"]), _report(False, ["ko"])])))
    assert "con ricerca semantica" in testo and "senza ricerca semantica" in testo
    assert "#1" in testo
