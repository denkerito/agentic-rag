"""Risultati di query_sql: interi entro il limite di caratteri, altrimenti anteprima con profilo."""

import json
from datetime import date
from decimal import Decimal as D

from agentic_rag.agent import config
from agentic_rag.agent.tools import componi_risultato, profilo_colonne

COLONNE = ["id", "data", "importo", "controparte", "fonti"]


def _righe(n: int) -> list[tuple]:
    return [
        (
            f"FATT-P-2025-{i:04d}",
            date(2025, 1 + i % 12, 1),
            D(f"{100 + i}.50"),
            f"FOR-00{i % 3}",
            [f"MOV-{i:06d}"],
        )
        for i in range(1, n + 1)
    ]


def test_risultato_piccolo_intero() -> None:
    r = componi_risultato(COLONNE, _righe(3), letto_tutto=True)
    assert r["troncato"] is False and r["n_righe"] == 3 and len(r["righe"]) == 3
    assert "anteprima" not in r and "profilo" not in r
    assert r["righe"][0] == ["FATT-P-2025-0001", "2025-02-01", "101.50", "FOR-001", ["MOV-000001"]]


def test_oltre_il_limite_diventa_anteprima() -> None:
    righe = _righe(2000)
    r = componi_risultato(COLONNE, righe, letto_tutto=True)
    assert r["troncato"] is True and "righe" not in r
    assert len(r["anteprima"]) == config.SQL_RIGHE_ANTEPRIMA == r["n_righe"]
    assert r["totale_righe"] == 2000 and r["totale_esatto"] is True
    assert "anteprima" in r["nota"] and "2000" in r["nota"].replace(".", "")
    assert set(r["profilo"]) == set(COLONNE)
    # l'anteprima costa molto meno del limite
    assert len(json.dumps(r, ensure_ascii=False)) < config.SQL_MAX_CARATTERI / 4


def test_il_limite_e_in_caratteri_non_in_righe() -> None:
    # 200 righe strette stanno nel limite: arrivano intere (prima si tagliava a 50 righe)
    strette = [(i, D(i)) for i in range(200)]
    r = componi_risultato(["n", "v"], strette, letto_tutto=True)
    assert r["troncato"] is False and r["n_righe"] == 200
    assert len(json.dumps(r, ensure_ascii=False)) <= config.SQL_MAX_CARATTERI


def test_totale_non_esatto_oltre_il_tetto_di_lettura() -> None:
    r = componi_risultato(COLONNE, _righe(2000), letto_tutto=False)
    assert r["totale_esatto"] is False and "più di" in r["nota"]


def test_profilo_per_tipo_di_colonna() -> None:
    profilo, per_raggruppare = profilo_colonne(COLONNE, _righe(30))
    assert profilo["id"]["distinti"] == 30 and "valori" not in profilo["id"]
    assert profilo["data"] == {"distinti": 12, "nulli": 0, "min": "2025-01-01", "max": "2025-12-01"}
    assert profilo["importo"]["min"] == "101.50" and profilo["importo"]["max"] == "130.50"
    assert profilo["importo"]["somma"] == str(sum(D(f"{100 + i}.50") for i in range(1, 31)))
    assert profilo["controparte"]["valori"] == ["FOR-000", "FOR-001", "FOR-002"]
    assert profilo["fonti"] == {"distinti": 30, "nulli": 0, "lunghezza_min": 1, "lunghezza_max": 1}
    assert per_raggruppare == ["data", "controparte"]  # 2-20 valori distinti, ordine delle colonne


def test_profilo_conta_i_nulli() -> None:
    profilo, _ = profilo_colonne(["x"], [(None,), (D(1),), (None,)])
    assert profilo["x"]["nulli"] == 2 and profilo["x"]["distinti"] == 1
