"""Lettura tollerante del ground truth (domande_test.yaml, storie.yaml)."""

import re
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from agentic_rag import config
from agentic_rag.agent.ids import extract_ids

GROUND_TRUTH_DIR: Path = config.ROOT_DIR / "eval" / "ground_truth"
STORIA_RE = re.compile(r"^[A-Z]{2}-\d{2}")


class Modalita(StrEnum):
    """Comportamento atteso dall'agente, ricavato dal campo `tipo`."""

    NORMALE = "normale"
    ONESTA = "onesta"  # la causa non è documentata: l'agente deve dirlo
    NON_RISPONDIBILE = "non_rispondibile"  # i dati non permettono di rispondere
    REGOLARE = "regolare"  # nessuna anomalia: l'esito è "regolare"


# (sottostringa di `tipo` in minuscolo, modalità): vale la prima che corrisponde
MODALITA_PER_TIPO: list[tuple[str, Modalita]] = [
    ("non rispondibile", Modalita.NON_RISPONDIBILE),
    ("non documentata", Modalita.ONESTA),
    ("regolare", Modalita.REGOLARE),
]


def modalita_di(tipo: str) -> Modalita:
    t = tipo.lower()
    return next((m for chiave, m in MODALITA_PER_TIPO if chiave in t), Modalita.NORMALE)


class Domanda(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    domanda: str
    storia_id: str | None = None
    tipo: str = ""
    risposta_attesa: str = ""
    fonti_attese: list[str] = Field(default_factory=list)
    query_sql: str | None = None

    @field_validator("fonti_attese", mode="before")
    @classmethod
    def _fonti(cls, v: Any) -> list[str]:
        return [str(x).strip() for x in (v or []) if str(x).strip()]

    @field_validator("query_sql", "storia_id", mode="before")
    @classmethod
    def _vuoto_e_none(cls, v: Any) -> Any:
        return v if v is None or str(v).strip() else None

    @property
    def storia_chiave(self) -> str | None:
        """`XX-99` se `storia_id` inizia con un ID di storia, altrimenti None (domanda generica)."""
        m = STORIA_RE.match(self.storia_id or "")
        return m.group(0) if m else None

    @property
    def modalita(self) -> Modalita:
        return modalita_di(self.tipo)

    @property
    def id_attesi(self) -> list[str]:
        return sorted({i for f in self.fonti_attese for i in extract_ids(f)})

    @property
    def tabelle_attese(self) -> list[str]:
        """Voci `nome.csv` → nome della tabella (`nome`)."""
        return sorted(
            {Path(f).stem.lower() for f in self.fonti_attese if f.lower().endswith(".csv")}
        )

    @property
    def fonti_non_riconosciute(self) -> list[str]:
        riconosciute = set(self.id_attesi)
        return [
            f
            for f in self.fonti_attese
            if not f.lower().endswith(".csv") and not (extract_ids(f) & riconosciute)
        ]


class Storia(BaseModel):
    model_config = ConfigDict(
        extra="allow"
    )  # evidenze_id e numeri_chiave variano da storia a storia

    id: str
    titolo: str = ""


class GroundTruth(BaseModel):
    domande: list[Domanda]
    storie: list[Storia] = Field(default_factory=list)

    def storia_nota(self, domanda: Domanda) -> bool:
        return domanda.storia_chiave is not None and domanda.storia_chiave in {
            s.id for s in self.storie
        }


def _leggi(path: Path, chiave: str) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"File di ground truth mancante: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    voci = data.get(chiave) if isinstance(data, dict) else data
    if not isinstance(voci, list):
        raise TypeError(f"{path.name}: attesa una lista di elementi sotto la chiave '{chiave}'")
    return voci


def carica(directory: Path = GROUND_TRUTH_DIR) -> GroundTruth:
    domande = [
        Domanda.model_validate(d) for d in _leggi(directory / "domande_test.yaml", "domande")
    ]
    try:
        storie = [Storia.model_validate(s) for s in _leggi(directory / "storie.yaml", "storie")]
    except FileNotFoundError:
        storie = []  # le storie servono solo per raggruppare: senza, si raggruppa per `storia_id`
    ids = [d.id for d in domande]
    if len(ids) != len(set(ids)):
        raise ValueError("domande_test.yaml: id delle domande duplicati")
    return GroundTruth(domande=domande, storie=storie)
