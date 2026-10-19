import csv
import json

import pytest

from agentic_rag.agent.output import Risposta
from agentic_rag.eval import etichette
from agentic_rag.eval.esperimento import (
    ErroreEsperimento,
    analizza_variante,
    crea_manifesto,
    esegui_esperimento,
    hash_ground_truth,
    leggi_jsonl,
    verifica_ripresa,
)
from agentic_rag.eval.groundtruth import Domanda
from agentic_rag.eval.runner import RisultatoDomanda

STATO = {"src": "s", "ground_truth": "g", "domande": [1, 2], "limiti": {"timeout_lavoro_s": 300}}


def _domande() -> list[Domanda]:
    return [
        Domanda(id=1, domanda="Q1", tipo="normale", risposta_attesa="r1", fonti_attese=["CTR-001"]),
        Domanda(
            id=2, domanda="Q2", tipo="risposta onesta: causa non documentata", risposta_attesa="r2"
        ),
    ]


def _manifesto(ripetizioni: int = 2, giudice: str | None = None) -> dict:
    varianti = [analizza_variante("con:semantica=1"), analizza_variante("senza:semantica=0")]
    return crea_manifesto("esp", varianti, ripetizioni, giudice, None, STATO)


def _ok(d: Domanda, *_):
    risposta = Risposta(conclusione="c", fonti=[], confidenza="alta", causa_documentata=False)
    return RisultatoDomanda(d, "ok", risposta=risposta, richieste=3)


def test_varianti() -> None:
    v = analizza_variante("grande:modello=anthropic:x,semantica=0")
    assert v == {"nome": "grande", "modello": "anthropic:x", "semantica": False}
    with pytest.raises(ErroreEsperimento):
        analizza_variante("x:temperatura=1")


def test_ordine_alternato_e_ripresa_dopo_interruzione(tmp_path) -> None:
    m = _manifesto()
    pub, priv = tmp_path / "pub", tmp_path / "priv"
    eseguite: list[tuple[str, int]] = []
    chiamate = {"n": 0}

    def interrotto(d, variante, *_):
        chiamate["n"] += 1
        if chiamate["n"] == 4:
            raise KeyboardInterrupt
        eseguite.append((variante["nome"], d.id))
        return _ok(d)

    with pytest.raises(KeyboardInterrupt):
        esegui_esperimento(m, _domande(), pub, priv, interrotto, pausa=0)
    assert len(leggi_jsonl(pub / "esecuzioni.jsonl")) == 3  # le concluse sono su disco

    def normale(d, variante, *_):
        eseguite.append((variante["nome"], d.id))
        return _ok(d)

    esegui_esperimento(m, _domande(), pub, priv, normale, pausa=0)
    righe = leggi_jsonl(pub / "esecuzioni.jsonl")
    assert len(righe) == 8 and len({(r["variante"], r["ripetizione"], r["id"]) for r in righe}) == 8
    # ripetizione 1: con, con, senza, senza; poi ripetizione 2
    assert eseguite[:4] == [("con", 1), ("con", 2), ("senza", 1), ("senza", 2)]
    assert len(leggi_jsonl(priv / "esecuzioni.jsonl")) == 8


def test_errore_di_infrastruttura_resta_aperto_e_si_recupera_alla_fine(tmp_path) -> None:
    m = _manifesto(ripetizioni=1)
    tentativi = {"n": 0}

    def instabile(d, variante, *_):
        if variante["nome"] == "senza" and d.id == 2:
            tentativi["n"] += 1
            if tentativi["n"] < 3:
                return RisultatoDomanda(
                    d, "errore", errore="ModelHTTPError 503", stato="errore_infrastruttura"
                )
        return _ok(d)

    esegui_esperimento(m, _domande(), tmp_path, tmp_path / "p", instabile, pausa=0)
    righe = [r for r in leggi_jsonl(tmp_path / "esecuzioni.jsonl") if r["variante"] == "senza"]
    assert [(r["id"], r["tentativo"], r["stato"]) for r in righe] == [
        (1, 1, "completata"),
        (2, 1, "errore_infrastruttura"),
        (2, 2, "errore_infrastruttura"),  # primo passaggio finale
        (2, 3, "completata"),  # secondo passaggio finale
    ]


def test_ripresa_rifiuta_codice_o_ground_truth_diversi() -> None:
    m = _manifesto()
    verifica_ripresa(m, dict(STATO))
    with pytest.raises(ErroreEsperimento, match="ground_truth"):
        verifica_ripresa(m, STATO | {"ground_truth": "altro"})
    with pytest.raises(ErroreEsperimento, match="src"):
        verifica_ripresa(m, STATO | {"src": "altro"})


def test_hash_del_ground_truth(tmp_path) -> None:
    (tmp_path / "a.yaml").write_text("x: 1", encoding="utf-8")
    h = hash_ground_truth(tmp_path)
    assert h == hash_ground_truth(tmp_path)
    (tmp_path / "a.yaml").write_text("x: 2", encoding="utf-8")
    assert h != hash_ground_truth(tmp_path)


def test_criterio_con_varianti_inesistenti() -> None:
    v = [analizza_variante("con:")]
    with pytest.raises(ErroreEsperimento):
        crea_manifesto("esp", v, 1, None, "task_success_rate:con-senza>=10", STATO)


def test_foglio_alla_cieca_e_kappa(tmp_path) -> None:
    righe = []
    for i, verdetto in enumerate(["corretta", "errata", "corretta", "parziale"], start=1):
        righe.append(
            {
                "variante": "con",
                "ripetizione": 1,
                "id": i,
                "stato": "completata",
                "modalita": "normale",
                "domanda": f"Q{i}",
                "risposta_attesa": f"r{i}",
                "risposta": {"conclusione": "c", "causa_documentata": False, "limiti": None},
                "conteggi": {"giudice": verdetto},
            }
        )
    (tmp_path / "esecuzioni.jsonl").write_text(
        "\n".join(json.dumps(r) for r in righe), encoding="utf-8"
    )
    path, n = etichette.esporta(tmp_path, 10)
    assert n == 4
    with path.open(encoding="utf-8", newline="") as f:
        foglio = list(csv.DictReader(f))
    assert "giudice" not in foglio[0] and all(r["etichetta_umana"] == "" for r in foglio)
    umane = {"con|1|1": "corretta", "con|1|2": "errata", "con|1|3": "errata", "con|1|4": "parziale"}
    for r in foglio:
        r["etichetta_umana"] = umane[r["chiave"]]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=etichette.COLONNE)
        w.writeheader()
        w.writerows(foglio)
    k = etichette.calcola_kappa(tmp_path)
    assert k["campione"] == 4 and k["accordo"] == 0.75
