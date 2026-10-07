"""Le query attese girano su un SQLite in memoria costruito dai CSV (dati sintetici nei test)."""

from decimal import Decimal as D

from agentic_rag.eval.numeri import esegui_query_attesa

CSV = (
    "id,data,controparte_id,imponibile,piva\n"
    "F1,2025-01-31,CLI-001,100.50,02489110372\n"
    "F2,2025-02-28,CLI-001,200.00,02489110372\n"
    "F3,2025-02-15,CLI-002,50,\n"
)


def _dir(tmp_path):
    (tmp_path / "fatture.csv").write_text(CSV, encoding="utf-8")
    return tmp_path


def test_query_attesa_su_csv_in_sqlite(tmp_path) -> None:
    q = esegui_query_attesa(
        "SELECT strftime('%Y-%m', data) AS mese, SUM(imponibile) AS tot FROM fatture "
        "GROUP BY 1 ORDER BY 1",
        _dir(tmp_path),
    )
    assert q is not None and q.errore is None and q.n_righe == 2
    assert q.valori == {D("100.5"), D("250.0")}  # le stringhe (il mese) non contano


def test_i_codici_con_zeri_iniziali_restano_testo(tmp_path) -> None:
    q = esegui_query_attesa("SELECT piva FROM fatture WHERE id = 'F1'", _dir(tmp_path))
    assert q is not None and q.valori == set() and q.n_righe == 1


def test_assenza_ed_errori(tmp_path) -> None:
    csv_dir = _dir(tmp_path)
    assert esegui_query_attesa(None, csv_dir) is None
    assert esegui_query_attesa("", csv_dir) is None
    sbagliata = esegui_query_attesa("SELECT x FROM inesistente", csv_dir)
    assert sbagliata is not None and sbagliata.errore == "OperationalError"
    scrittura = esegui_query_attesa("DELETE FROM fatture", csv_dir)
    assert scrittura is not None and scrittura.errore is not None  # PRAGMA query_only


def test_query_senza_tabelle_non_richiede_i_csv(tmp_path) -> None:
    q = esegui_query_attesa("SELECT 1", tmp_path / "non_esiste")
    assert q is not None and q.valori == {D(1)}
