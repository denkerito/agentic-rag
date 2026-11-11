import psycopg
import pytest

from agentic_rag import config
from agentic_rag.eval import recupero
from agentic_rag.eval.recupero import (
    documenti_in_ordine,
    misura,
    precision_at_k,
    query_or,
    recall_at_k,
    reciprocal_rank,
)


def test_precision_e_recall_su_casi_noti() -> None:
    classifica = ["DOC-A", "DOC-B", "DOC-C", "DOC-D", "DOC-E"]
    pertinenti = {"DOC-C", "DOC-Z"}
    assert precision_at_k(classifica, pertinenti, 1) == 0.0
    assert precision_at_k(classifica, pertinenti, 3) == pytest.approx(1 / 3)
    assert recall_at_k(classifica, pertinenti, 3) == 0.5
    assert recall_at_k(classifica, pertinenti, 1) == 0.0


def test_precision_divide_per_k_anche_con_classifica_corta() -> None:
    # una ricerca con soglia può restituire meno di k documenti: i posti vuoti contano come errori
    assert precision_at_k(["DOC-A"], {"DOC-A"}, 5) == 0.2


def test_reciprocal_rank() -> None:
    assert reciprocal_rank(["DOC-A", "DOC-B", "DOC-C"], {"DOC-C"}) == pytest.approx(1 / 3)
    assert reciprocal_rank(["DOC-A", "DOC-B"], {"DOC-B", "DOC-A"}) == 1.0
    assert reciprocal_rank(["DOC-A"], {"DOC-X"}) == 0.0
    assert reciprocal_rank([], {"DOC-X"}) == 0.0


def test_documenti_in_ordine_del_chunk_migliore() -> None:
    assert documenti_in_ordine(["DOC-B", "DOC-A", "DOC-B", "DOC-C", "DOC-A"]) == [
        "DOC-B",
        "DOC-A",
        "DOC-C",
    ]


def test_query_or_unisce_le_parole() -> None:
    assert query_or("Quanto costa l'affitto di Via Tortona?") == (
        "Quanto or costa or l or affitto or di or Via or Tortona"
    )


def test_misura_media_sulle_domande_e_differenza_appaiata() -> None:
    pertinenti = {1: {"DOC-A"}, 2: {"DOC-B"}}
    classifiche = {
        "semantica": {1: ["DOC-A"], 2: ["DOC-X", "DOC-B"]},
        "testuale": {1: ["DOC-X"], 2: ["DOC-B"]},
    }
    out = misura(classifiche, pertinenti, riferimento="testuale")
    assert out["domande"] == 2
    assert out["sistemi"]["semantica"]["mrr"]["valore"] == pytest.approx(0.75)
    assert out["sistemi"]["testuale"]["mrr"]["valore"] == pytest.approx(0.5)
    assert out["differenze"]["semantica - testuale"]["mrr"]["valore"] == pytest.approx(0.25)
    assert "testuale - testuale" not in out["differenze"]


@pytest.mark.integration
def test_classifiche_sul_database_reale(monkeypatch) -> None:
    try:
        conn = psycopg.connect(config.DATABASE_URL_AGENT, connect_timeout=3)
    except psycopg.Error:
        pytest.skip("database non raggiungibile")
    # embedding finto: nessuna chiamata a Gemini, conta solo che le classifiche girino sul DB
    monkeypatch.setattr("agentic_rag.rag.search.embed_query", lambda testo: [0.01] * 768)
    with conn:
        esistenti = {r[0] for r in conn.execute("SELECT doc_id FROM documenti")}
        classifiche = recupero.classifiche(conn, "canone Nimbus aumento listino")
        assert set(classifiche) == set(recupero.SISTEMI)
        for nome, docs in classifiche.items():
            assert len(docs) == len(set(docs)) <= recupero.PROFONDITA, nome
            assert set(docs) <= esistenti, nome
        assert classifiche["testuale"], "la ricerca testuale trova i documenti Nimbus"
