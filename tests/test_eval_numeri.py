from decimal import Decimal as D

import pytest

from agentic_rag.agent.output import Numero, Risposta
from agentic_rag.eval.numeri import (
    MetricheNumeri,
    RisultatoQuery,
    corrisponde,
    estrai_numeri,
    valuta_numeri,
)


@pytest.mark.parametrize(
    ("testo", "atteso"),
    [
        ("41.200,00 €", D("41200.00")),
        ("41,200.00", D("41200.00")),
        ("41200.00", D("41200.00")),
        ("12,5%", D("12.5")),
        ("-1.234,5", D("-1234.5")),
        ("1 234,56", D("1234.56")),
        ("7", D(7)),
        ("34 %", D(34)),
    ],
)
def test_estrai_numeri_formati_it_en(testo, atteso) -> None:
    assert atteso in estrai_numeri(testo)


def test_token_ambiguo_produce_entrambe_le_letture() -> None:
    assert {D(1234), D("1.234")} <= estrai_numeri("1.234")


def test_piu_numeri_in_un_testo_e_nessuno() -> None:
    assert {D(100), D(2025)} <= estrai_numeri("da 100 a 2025")
    assert estrai_numeri("nessun numero qui") == set()


@pytest.mark.parametrize(
    ("atteso", "trovato", "ok"),
    [
        (D("100.004"), D("100.00"), True),  # entro 0,01
        (D("12.4987"), D("12.5"), True),  # arrotondato a 1 decimale dall'agente
        (D("12.49"), D(12), True),  # arrotondato all'intero
        (D("12.6"), D(12), False),
        (D(100), D(101), False),
    ],
)
def test_corrisponde(atteso, trovato, ok) -> None:
    assert corrisponde(atteso, trovato) is ok


def _r(conclusione: str = "c", valori: list[str] | None = None) -> Risposta:
    return Risposta(
        conclusione=conclusione,
        fonti=[],
        confidenza="alta",
        causa_documentata=False,
        numeri=[Numero(descrizione="d", valore=v, fonti=[]) for v in (valori or [])],
    )


def test_valuta_numeri_trovati_e_mancanti() -> None:
    atteso = RisultatoQuery(valori={D(41200), D("52870.5"), D("12.4987")}, n_righe=1)
    m = valuta_numeri(atteso, _r("Il costo è 52.870,50 €", ["41.200,00 €"]))
    assert (m.attesi, m.trovati) == (3, 2) and m.recall == pytest.approx(2 / 3)
    assert m.mancanti == ["12.4987"]


def test_i_numeri_nella_conclusione_contano() -> None:
    m = valuta_numeri(RisultatoQuery(valori={D(8)}, n_righe=1), _r("Sono 8 fatture"))
    assert m.recall == 1.0


@pytest.mark.parametrize(
    ("atteso", "frammento"),
    [
        (None, "nessuna query"),
        (RisultatoQuery(errore="UndefinedTable"), "non eseguibile"),
        (RisultatoQuery(valori=set(), n_righe=3), "non restituisce numeri"),
        (RisultatoQuery(valori={D(i) for i in range(30)}, n_righe=30), "più di"),
    ],
)
def test_controllo_non_applicabile(atteso, frammento) -> None:
    m: MetricheNumeri = valuta_numeri(atteso, _r())
    assert not m.applicabile and frammento in (m.motivo_na or "") and m.recall is None
