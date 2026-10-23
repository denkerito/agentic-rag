"""Prova dell'assenza: un'affermazione «non esiste» cita una query completa con risultato vuoto o a zero."""

from decimal import Decimal as D

import pytest
from pydantic_ai import ModelRetry

from agentic_rag.agent.agent import MOTIVI_RIFIUTO, RIFIUTO_ASSENZA_NON_PROVATA, check_risposta
from agentic_rag.agent.output import Assenza, Risposta
from agentic_rag.agent.tools import prova_assenza


@pytest.mark.parametrize(
    ("righe", "prova"),
    [
        ([], True),  # HAVING count(*) > 1 senza righe
        ([(0,)], True),  # COUNT(*) = 0
        ([("stesso numero", 0), ("stesso importo", D(0))], True),  # etichette e conteggi a zero
        ([(3,)], False),  # ci sono casi
        ([("stesso numero", 0), ("stesso importo", 2)], False),
        ([("FATT-P-2025-0001",), ("FATT-P-2025-0002",)], False),  # un elenco non prova nulla
        ([(None,)], False),
    ],
)
def test_prova_assenza(righe, prova) -> None:
    assert prova_assenza(righe) is prova


def _risposta(*assenze: Assenza) -> Risposta:
    return Risposta(
        conclusione="Nessuna fattura pagata due volte.",
        fonti=[],
        confidenza="media",
        causa_documentata=False,
        assenze=list(assenze),
    )


QUERY = {
    "Q1": {"sql": "SELECT ...", "completo": True, "zero": True},
    "Q2": {"sql": "SELECT ...", "completo": False, "zero": False},
    "Q3": {"sql": "SELECT ...", "completo": True, "zero": False},
}


def test_assenza_provata_da_query_completa_e_a_zero() -> None:
    check_risposta(
        _risposta(Assenza(affermazione="nessun doppio pagamento", query_id="Q1")),
        set(),
        set(),
        QUERY,
    )


@pytest.mark.parametrize(
    ("query_id", "frammento"),
    [("Q9", "inesistente"), ("Q2", "anteprima"), ("Q3", "restituisce righe")],
)
def test_assenza_non_provata(query_id, frammento) -> None:
    r = _risposta(Assenza(affermazione="nessun doppio pagamento", query_id=query_id))
    with pytest.raises(ModelRetry) as e:
        check_risposta(r, set(), set(), QUERY)
    assert str(e.value).startswith(RIFIUTO_ASSENZA_NON_PROVATA) and frammento in str(e.value)


def test_senza_assenze_nessun_controllo() -> None:
    check_risposta(_risposta(), set(), set())


def test_motivo_registrato_senza_prefissi_in_conflitto() -> None:
    assert MOTIVI_RIFIUTO["assenza_non_provata"] == RIFIUTO_ASSENZA_NON_PROVATA
    prefissi = list(MOTIVI_RIFIUTO.values())
    assert not any(a != b and b.startswith(a) for a in prefissi for b in prefissi)


def test_schema_definisce_confidenza_e_assenze() -> None:
    campi = Risposta.model_json_schema()["properties"]
    assert "bassa" in campi["confidenza"]["description"]
    assert "non rispondibile" in campi["confidenza"]["description"]
    assert "query" in campi["assenze"]["description"]
