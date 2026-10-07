import pytest

from agentic_rag.agent.output import Numero, Risposta
from agentic_rag.eval.fonti import VISTE, id_citati, tabelle_in_sql, tabelle_lette, valuta_fonti
from agentic_rag.eval.groundtruth import Domanda


def test_tabelle_in_sql_esclude_le_cte_e_vede_i_join() -> None:
    sql = "WITH x AS (SELECT * FROM fatture) SELECT * FROM x JOIN clienti c ON c.id = x.cliente_id"
    assert tabelle_in_sql(sql) == {"fatture", "clienti"}


def test_sql_non_valida_non_fa_crollare_nulla() -> None:
    assert tabelle_in_sql("SELEC rotto (") == set()


def test_le_viste_si_espandono_nelle_tabelle_base() -> None:
    trace = [{"kind": "sql", "sql": "SELECT * FROM v_margine_mensile"}]
    letti = tabelle_lette(trace)
    assert "v_margine_mensile" in letti and VISTE["v_margine_mensile"] <= letti
    assert "scritture_contabili" in letti and "contratti" not in letti


def test_i_tool_sui_documenti_contano_come_lettura_di_documenti() -> None:
    assert tabelle_lette([{"kind": "cerca_documenti"}]) == {"documenti", "documenti_chunks"}
    assert tabelle_lette([{"kind": "apri_documento"}]) == {"documenti"}


def _risposta(fonti: list[str], numeri: list[Numero] | None = None) -> Risposta:
    return Risposta(
        conclusione="c",
        fonti=fonti,
        numeri=numeri or [],
        confidenza="alta",
        causa_documentata=False,
    )


def test_id_citati_unisce_fonti_e_numeri() -> None:
    r = _risposta(["CTR-001"], [Numero(descrizione="x", valore="1", fonti=["MOV-000001"])])
    assert id_citati(r) == {"CTR-001", "MOV-000001"}


def test_valuta_fonti_recall_extra_e_mancanti() -> None:
    d = Domanda.model_validate(
        {
            "id": 1,
            "domanda": "q",
            "fonti_attese": ["CTR-001", "FATT-P-2025-0001", "fatture.csv", "contratti.csv"],
        }
    )
    r = _risposta(["CTR-001", "DOC-EML-001"])
    trace = [{"kind": "sql", "sql": "SELECT * FROM fatture"}]
    m = valuta_fonti(d, r, trace, seen_ids={"CTR-001", "DOC-EML-001"})
    assert (m.id_attesi, m.id_trovati, m.id_extra) == (2, 1, 1)
    assert m.id_recall == 0.5 and m.id_mancanti == ["FATT-P-2025-0001"]
    assert (m.tabelle_attese, m.tabelle_trovate) == (2, 1) and m.tabelle_mancanti == ["contratti"]
    assert m.citate_non_viste == 0


def test_citate_non_viste_e_recall_non_applicabile() -> None:
    d = Domanda.model_validate({"id": 1, "domanda": "q"})
    m = valuta_fonti(d, _risposta(["CTR-001"]), [], seen_ids=set())
    assert m.citate_non_viste == 1 and m.id_recall is None and m.tabelle_recall is None


@pytest.mark.integration
def test_la_mappa_delle_viste_coincide_con_il_database() -> None:
    import psycopg

    from agentic_rag import config

    try:
        conn = psycopg.connect(config.DATABASE_URL_AGENT, connect_timeout=3, autocommit=True)
    except psycopg.Error:
        pytest.skip("database non raggiungibile")
    with conn:
        viste = {
            r[0] for r in conn.execute("SELECT viewname FROM pg_views WHERE schemaname='public'")
        }

        def basi(vista: str) -> set[str]:
            definizione = conn.execute("SELECT pg_get_viewdef(%s::regclass)", (vista,)).fetchone()[
                0
            ]
            out: set[str] = set()
            for nome in tabelle_in_sql(definizione):
                out |= basi(nome) if nome in viste else {nome}
            return out

        assert viste == set(VISTE)
        for v in viste:
            assert basi(v) == set(VISTE[v]), v
