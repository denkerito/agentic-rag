"""Tutti i dati sono sintetici e inventati: i test non leggono eval/ground_truth/."""

from pathlib import Path

import pytest
import yaml

from agentic_rag.eval.groundtruth import Domanda, Modalita, carica, modalita_di


def _scrivi(tmp_path: Path, domande: list[dict], storie: list[dict] | None = None) -> Path:
    (tmp_path / "domande_test.yaml").write_text(
        yaml.safe_dump({"domande": domande}, allow_unicode=True), encoding="utf-8"
    )
    if storie is not None:
        (tmp_path / "storie.yaml").write_text(
            yaml.safe_dump({"storie": storie}, allow_unicode=True), encoding="utf-8"
        )
    return tmp_path


def _d(**kw) -> dict:
    base = {"id": 1, "domanda": "d?", "storia_id": "ZZ-01", "tipo": "x", "risposta_attesa": "r"}
    return base | kw


def test_carica_e_tollera_campi_extra_e_storie_diverse(tmp_path) -> None:
    gt = carica(
        _scrivi(
            tmp_path,
            [_d(campo_nuovo=1)],
            [
                {
                    "id": "ZZ-01",
                    "titolo": "t",
                    "numeri_chiave": {"a": 1.5},
                    "evidenze_id": {"x": "CTR-001"},
                },
                {"id": "ZZ-02", "altro": [1, 2]},
            ],
        )
    )
    assert len(gt.domande) == 1 and len(gt.storie) == 2
    assert gt.storia_nota(gt.domande[0])


@pytest.mark.parametrize(
    ("storia_id", "chiave"),
    [
        ("ZZ-01", "ZZ-01"),
        ("ZZ-02 + altra storia", "ZZ-02"),
        ("generale", None),
        (None, None),
        ("", None),
    ],
)
def test_storia_chiave_tollera_i_tre_formati(storia_id, chiave) -> None:
    assert Domanda.model_validate(_d(storia_id=storia_id)).storia_chiave == chiave


def test_fonti_separano_id_tabelle_e_non_riconosciute() -> None:
    d = Domanda.model_validate(
        _d(fonti_attese=["FATT-P-2025-0001", "CTR-001", "fatture_righe.csv", "Clienti.CSV", "boh"])
    )
    assert d.id_attesi == ["CTR-001", "FATT-P-2025-0001"]
    assert d.tabelle_attese == ["clienti", "fatture_righe"]
    assert d.fonti_non_riconosciute == ["boh"]


def test_fonti_e_query_vuote() -> None:
    d = Domanda.model_validate(_d(fonti_attese=None, query_sql="  "))
    assert d.fonti_attese == [] and d.query_sql is None


@pytest.mark.parametrize(
    ("tipo", "modalita"),
    [
        ("risposta onesta: causa non documentata", Modalita.ONESTA),
        ("Non rispondibile", Modalita.NON_RISPONDIBILE),
        ("esito: regolare", Modalita.REGOLARE),
        ("multi-passo", Modalita.NORMALE),
        ("", Modalita.NORMALE),
    ],
)
def test_modalita_dal_tipo(tipo, modalita) -> None:
    assert modalita_di(tipo) == modalita


def test_errori_chiari(tmp_path) -> None:
    with pytest.raises(FileNotFoundError, match="domande_test.yaml"):
        carica(tmp_path)
    with pytest.raises(ValueError, match="duplicati"):
        carica(_scrivi(tmp_path, [_d(), _d()]))


def test_senza_storie_si_prosegue(tmp_path) -> None:
    gt = carica(_scrivi(tmp_path, [_d()]))
    assert gt.storie == [] and not gt.storia_nota(gt.domande[0])
