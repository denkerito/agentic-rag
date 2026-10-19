"""Statistica degli esperimenti: funzioni pure, nessun I/O.

- media per domanda, poi media sulle domande (ogni domanda pesa uguale);
- intervallo al 95% con bootstrap percentile ricampionando le domande (seme fisso: riproducibile);
- bootstrap appaiato sulla differenza tra due varianti;
- pass^k (τ-bench): probabilità che k esecuzioni indipendenti riescano tutte;
- κ di Cohen tra due etichettatori.
"""

import random
from collections import Counter
from collections.abc import Hashable, Sequence
from dataclasses import dataclass
from math import comb

B_BOOTSTRAP = 2000
SEME = 1234
LIVELLO = 0.95


@dataclass(frozen=True)
class Stima:
    valore: float | None  # None se nessuna domanda è applicabile
    basso: float | None
    alto: float | None
    domande: int  # domande che contribuiscono (il denominatore della media sulle domande)


def _media(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs)


def _percentile(ordinati: list[float], q: float) -> float:
    """Percentile con interpolazione lineare (come numpy, metodo `linear`)."""
    pos = (len(ordinati) - 1) * q
    i = int(pos)
    if i + 1 >= len(ordinati):
        return ordinati[-1]
    return ordinati[i] + (ordinati[i + 1] - ordinati[i]) * (pos - i)


def bootstrap(per_domanda: Sequence[float], b: int = B_BOOTSTRAP, seme: int = SEME) -> Stima:
    """Media sulle domande con intervallo bootstrap percentile al 95%."""
    if not per_domanda:
        return Stima(None, None, None, 0)
    valori = list(per_domanda)
    rng = random.Random(seme)
    n = len(valori)
    medie = sorted(_media([valori[rng.randrange(n)] for _ in range(n)]) for _ in range(b))
    coda = (1 - LIVELLO) / 2
    return Stima(_media(valori), _percentile(medie, coda), _percentile(medie, 1 - coda), n)


def bootstrap_appaiato(a: dict[Hashable, float], b: dict[Hashable, float], **kw: int) -> Stima:
    """Differenza a − b sulle sole domande presenti in entrambe."""
    comuni = sorted(set(a) & set(b), key=str)
    return bootstrap([a[k] - b[k] for k in comuni], **kw)


def pass_hat_k(n: int, c: int, k: int) -> float:
    """Stima non distorta di pass^k da n esecuzioni con c successi: C(c,k) / C(n,k)."""
    if n < k:
        raise ValueError("servono almeno k esecuzioni")
    return comb(c, k) / comb(n, k)


def kappa_cohen(a: Sequence[str], b: Sequence[str]) -> float | None:
    """κ di Cohen (non pesato). None se indefinito (accordo atteso pari a 1)."""
    if len(a) != len(b) or not a:
        raise ValueError("servono due sequenze non vuote della stessa lunghezza")
    n = len(a)
    osservato = sum(x == y for x, y in zip(a, b, strict=True)) / n
    ca, cb = Counter(a), Counter(b)
    atteso = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    if atteso == 1:
        return None
    return (osservato - atteso) / (1 - atteso)


def percentile(valori: Sequence[float], q: float) -> float | None:
    """Percentile q (0–1) dei valori, None se vuoti. Per la latenza p50/p95."""
    return _percentile(sorted(valori), q) if valori else None
