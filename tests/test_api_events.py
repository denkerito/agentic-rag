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


def test_sql_preview_has_total_and_visible_ids() -> None:
    content = {
        "colonne": ["id", "fornitore"],
        "anteprima": [["FATT-P-2025-0001", "FOR-001"]],
        "n_righe": 1,
        "totale_righe": 873,
        "totale_esatto": True,
        "troncato": True,
        "profilo": {"fornitore": {"distinti": 2, "nulli": 0, "valori": ["FOR-001", "FOR-002"]}},
        "colonne_per_raggruppare": ["fornitore"],
        "nota": "anteprima",
    }
    ev = tradurre(FunctionToolResultEvent(ToolReturnPart("query_sql", content, "c1")))
    assert isinstance(ev, ToolResult)
    assert (ev.n_righe, ev.totale, ev.troncato) == (1, 873, True)
    assert ev.ids == ["FATT-P-2025-0001", "FOR-001", "FOR-002"]
    assert "anteprima" not in ev.model_dump()


def test_legacy_search_result_lists_doc_ids() -> None:
    # cerca_documenti: nome della ricerca semantica nelle indagini salvate prima della rinomina
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


def test_list_result_has_ids_and_paging_but_no_titles() -> None:
    content = {
        "totale": 31,
        "pagina": 2,
        "pagine": 2,
        "documenti": [{"doc_id": "DOC-EML-001", "titolo": "Email riservata", "tipo": "email"}],
    }
    ev = tradurre(FunctionToolResultEvent(ToolReturnPart("elenca_documenti", content, "c4")))
    assert isinstance(ev, ToolResult) and ev.ids == ["DOC-EML-001"]
    assert (ev.totale, ev.pagina, ev.pagine) == (31, 2, 2)
    assert "Email riservata" not in ev.model_dump_json()


def test_text_search_result_has_counts_but_no_fragments() -> None:
    content = {
        "totale": 7,
        "risultati": [
            {"doc_id": "CTR-001", "frammenti": "canone «Nimbus»"},
            {"doc_id": "DOC-EML-003", "frammenti": "x"},
        ],
    }
    ev = tradurre(FunctionToolResultEvent(ToolReturnPart("cerca_testo", content, "c5")))
    assert isinstance(ev, ToolResult) and ev.ids == ["CTR-001", "DOC-EML-003"]
    assert (ev.n_pertinenti, ev.totale) == (2, 7)
    assert "Nimbus" not in ev.model_dump_json()


def test_text_search_without_matches() -> None:
    content = {"totale": 0, "risultati": [], "nota": "Nessun documento contiene questi termini."}
    ev = tradurre(FunctionToolResultEvent(ToolReturnPart("cerca_testo", content, "c5")))
    assert isinstance(ev, ToolResult) and ev.ids == [] and (ev.n_pertinenti, ev.totale) == (0, 0)


def test_semantic_search_result_lists_doc_ids() -> None:
    content = {"risultati": [{"doc_id": "DOC-EML-003", "testo": "x"}]}
    ev = tradurre(FunctionToolResultEvent(ToolReturnPart("cerca_semantica", content, "c6")))
    assert isinstance(ev, ToolResult) and ev.ids == ["DOC-EML-003"] and ev.n_pertinenti == 1
    assert "testo" not in ev.model_dump_json()
