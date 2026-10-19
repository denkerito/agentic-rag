import pytest

from agentic_rag.eval.statistica import (
    bootstrap,
    bootstrap_appaiato,
    kappa_cohen,
    pass_hat_k,
    percentile,
)


def test_pass_hat_k_su_valori_calcolati_a_mano() -> None:
    assert pass_hat_k(5, 5, 3) == 1.0
    assert pass_hat_k(5, 3, 3) == pytest.approx(1 / 10)  # C(3,3)/C(5,3)
    assert pass_hat_k(5, 2, 3) == 0.0
    assert pass_hat_k(4, 3, 1) == pytest.approx(0.75)  # con k=1 è il tasso di successo
    with pytest.raises(ValueError):
        pass_hat_k(2, 2, 3)


def test_kappa_di_cohen() -> None:
    # osservato 0.75, atteso (2*1 + 2*3)/16 = 0.5 → κ = 0.5
    assert kappa_cohen(["x", "x", "y", "y"], ["x", "y", "y", "y"]) == pytest.approx(0.5)
    assert kappa_cohen(["a", "b", "c"], ["a", "b", "c"]) == pytest.approx(1.0)
    assert kappa_cohen(["a", "a"], ["a", "a"]) is None  # una sola classe: indefinito
    with pytest.raises(ValueError):
        kappa_cohen(["a"], ["a", "b"])


def test_bootstrap_riproducibile_e_coerente() -> None:
    valori = [0.0, 1.0, 1.0, 0.5, 1.0, 0.0]
    a, b = bootstrap(valori), bootstrap(valori)
    assert a == b  # seme fisso
    assert a.valore == pytest.approx(sum(valori) / len(valori)) and a.domande == 6
    assert a.basso <= a.valore <= a.alto
    costante = bootstrap([0.8] * 5)
    assert costante.basso == pytest.approx(0.8) and costante.alto == pytest.approx(0.8)
    assert bootstrap([]).valore is None


def test_bootstrap_appaiato_usa_solo_le_domande_comuni() -> None:
    s = bootstrap_appaiato({1: 1.0, 2: 0.5, 3: 0.0}, {1: 0.5, 2: 0.5, 9: 1.0})
    assert s.domande == 2 and s.valore == pytest.approx(0.25)


def test_percentile() -> None:
    assert percentile([], 0.5) is None
    assert percentile([3, 1, 2], 0.5) == 2
    assert percentile([0, 10], 0.95) == pytest.approx(9.5)
