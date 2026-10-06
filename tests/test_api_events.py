from pydantic_ai.messages import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    OutputToolResultEvent,
    PartStartEvent,
    RetryPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)

from agentic_rag.api.events import tradurre
from agentic_rag.api.schemas import RispostaScartata, ToolCall, ToolResult, ToolRetry


def test_tool_call_carries_sql() -> None:
    part = ToolCallPart("query_sql", {"sql": "SELECT 1"}, tool_call_id="c1")
    ev = tradurre(FunctionToolCallEvent(part))
    assert ev == ToolCall(tool_call_id="c1", tool="query_sql", args={"sql": "SELECT 1"})


def test_sql_result_has_counts_and_ids_but_no_rows() -> None:
    content = {
        "colonne": ["id", "totale"],
        "righe": [["FATT-P-2025-0001", "10.00"], ["FATT-A-2025-0002", "20.00"]],
        "n_righe": 2,
        "troncato": False,
    }
    part = ToolReturnPart("query_sql", content, tool_call_id="c1")
    ev = tradurre(FunctionToolResultEvent(part))
    assert isinstance(ev, ToolResult)
    assert ev.ids == ["FATT-A-2025-0002", "FATT-P-2025-0001"]
    assert (ev.n_righe, ev.troncato) == (2, False)
    assert "righe" not in ev.model_dump() and "10.00" not in ev.model_dump_json()


def test_search_result_lists_doc_ids() -> None:
    content = {"risultati": [{"doc_id": "DOC-EML-003", "testo": "x"}, {"doc_id": "CTR-001"}]}
    ev = tradurre(FunctionToolResultEvent(ToolReturnPart("cerca_documenti", content, "c2")))
    assert isinstance(ev, ToolResult)
    assert ev.ids == ["CTR-001", "DOC-EML-003"] and ev.n_pertinenti == 2
    assert "testo" not in ev.model_dump_json()


def test_search_without_results() -> None:
    content = {"risultati": [], "nota": "Nessun documento pertinente"}
    ev = tradurre(FunctionToolResultEvent(ToolReturnPart("cerca_documenti", content, "c2")))
    assert isinstance(ev, ToolResult) and ev.ids == [] and ev.n_pertinenti == 0


def test_open_document_result() -> None:
    content = {"doc_id": "CTR-001", "offset": 0, "troncato": True, "contenuto": "testo lungo"}
    ev = tradurre(FunctionToolResultEvent(ToolReturnPart("apri_documento", content, "c3")))
    assert isinstance(ev, ToolResult)
    assert (ev.ids, ev.troncato, ev.offset) == (["CTR-001"], True, 0)
    assert "testo lungo" not in ev.model_dump_json()


def test_tool_retry_is_reported() -> None:
    part = RetryPromptPart(
        "Errore SQL: colonna inesistente", tool_name="query_sql", tool_call_id="c1"
    )
    ev = tradurre(FunctionToolResultEvent(part))
    assert isinstance(ev, ToolRetry) and "colonna inesistente" in ev.motivo


def test_rejected_answer_is_reported() -> None:
    part = RetryPromptPart("Fonti mai ricevute dai tool: FATT-P-2025-9999", tool_call_id="o1")
    ev = tradurre(OutputToolResultEvent(part))
    assert isinstance(ev, RispostaScartata) and "FATT-P-2025-9999" in ev.motivo


def test_text_and_other_events_are_ignored() -> None:
    assert tradurre(PartStartEvent(index=0, part=TextPart("ciao"))) is None
    ok = ToolReturnPart("final_result", "Final result processed.", tool_call_id="o1")
    assert tradurre(OutputToolResultEvent(ok)) is None
