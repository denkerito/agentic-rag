"""Contratto dell'API: richieste/risposte HTTP ed eventi degli step (persistiti e inviati via SSE)."""

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints

from agentic_rag.agent.output import Risposta

Stato = Literal["in_coda", "in_corso", "completata", "fallita", "interrotta"]
STATI_FINALI: frozenset[str] = frozenset({"completata", "fallita", "interrotta"})


class IndagineCreate(BaseModel):
    domanda: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class IndagineCreata(BaseModel):
    id: UUID
    stato: Stato


class IndagineRiga(BaseModel):
    id: UUID
    domanda: str
    stato: Stato
    creata_il: datetime
    conclusa_il: datetime | None


class IndagineDettaglio(IndagineRiga):
    modello: str
    iniziata_il: datetime | None
    risposta: Risposta | None
    errore: str | None
    utilizzo: dict[str, Any] | None


# Eventi: `tipo` è la colonna `tipo` e l'`event:` SSE; il resto finisce in `dati` / `data:`.
class ToolCall(BaseModel):
    tipo: Literal["tool_call"] = "tool_call"
    tool_call_id: str
    tool: str
    args: dict[str, Any]


class ToolResult(BaseModel):
    """Esito di un tool: conteggi e ID, mai le righe."""

    tipo: Literal["tool_result"] = "tool_result"
    tool_call_id: str
    tool: str
    ids: list[str] = Field(default_factory=list, description="ID fonte comparsi nel risultato")
    n_righe: int | None = None  # query_sql
    n_pertinenti: int | None = None  # cerca_documenti
    troncato: bool | None = None  # query_sql, apri_documento
    offset: int | None = None  # apri_documento


class ToolRetry(BaseModel):
    """Il tool ha rifiutato la chiamata (SQL non valida, doc inesistente): il modello riprova."""

    tipo: Literal["tool_retry"] = "tool_retry"
    tool_call_id: str
    tool: str
    motivo: str


class RispostaScartata(BaseModel):
    """Il validator ha rifiutato la risposta (fonti mai viste, numeri senza fonti, ...)."""

    tipo: Literal["risposta_scartata"] = "risposta_scartata"
    motivo: str


class RispostaFinale(BaseModel):
    tipo: Literal["risposta"] = "risposta"
    risposta: Risposta


class Errore(BaseModel):
    tipo: Literal["errore"] = "errore"
    errore: str
    messaggio: str


class Interrotta(BaseModel):
    tipo: Literal["interrotta"] = "interrotta"
    motivo: str


Evento = Annotated[
    ToolCall | ToolResult | ToolRetry | RispostaScartata | RispostaFinale | Errore | Interrotta,
    Field(discriminator="tipo"),
]
TIPI_TERMINALI: frozenset[str] = frozenset({"risposta", "errore", "interrotta"})
