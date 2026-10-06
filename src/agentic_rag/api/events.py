"""Traduzione degli eventi Pydantic AI negli eventi dell'API (funzione pura, nessun I/O)."""

from typing import Any

from pydantic_ai import AgentStreamEvent
from pydantic_ai.messages import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    OutputToolResultEvent,
    RetryPromptPart,
    ToolReturnPart,
)

from agentic_rag.agent.ids import extract_ids
from agentic_rag.api.schemas import (
    RispostaScartata,
    ToolCall,
    ToolResult,
    ToolRetry,
)

MAX_MOTIVO_CHARS = 500

EventoApi = ToolCall | ToolResult | ToolRetry | RispostaScartata


def _motivo(part: RetryPromptPart) -> str:
    return part.model_response()[:MAX_MOTIVO_CHARS]


def _tool_result(part: ToolReturnPart) -> ToolResult:
    content: Any = part.content
    base = {"tool_call_id": part.tool_call_id, "tool": part.tool_name}
    if not isinstance(content, dict):
        return ToolResult(**base)
    if part.tool_name == "query_sql":
        return ToolResult(
            **base,
            ids=sorted(extract_ids(str(content.get("righe", [])))),
            n_righe=content.get("n_righe"),
            troncato=content.get("troncato"),
        )
    if part.tool_name == "cerca_documenti":
        risultati = content.get("risultati", [])
        ids = sorted({r["doc_id"] for r in risultati})
        return ToolResult(**base, ids=ids, n_pertinenti=len(risultati))
    if part.tool_name == "apri_documento":
        return ToolResult(
            **base,
            ids=[content["doc_id"]],
            troncato=content.get("troncato"),
            offset=content.get("offset"),
        )
    return ToolResult(**base)


def tradurre(event: AgentStreamEvent) -> EventoApi | None:
    """Evento del framework -> evento API; None per quelli da non mostrare (delta di testo ecc.).

    La risposta finale non passa di qui: arriva solo con `AgentRunResultEvent`, già validata.
    """
    if isinstance(event, FunctionToolCallEvent):
        part = event.part
        return ToolCall(
            tool_call_id=part.tool_call_id, tool=part.tool_name, args=part.args_as_dict()
        )
    if isinstance(event, FunctionToolResultEvent):
        part = event.part
        if isinstance(part, RetryPromptPart):
            return ToolRetry(
                tool_call_id=part.tool_call_id, tool=part.tool_name or "", motivo=_motivo(part)
            )
        return _tool_result(part)
    if isinstance(event, OutputToolResultEvent) and isinstance(event.part, RetryPromptPart):
        return RispostaScartata(motivo=_motivo(event.part))
    return None
