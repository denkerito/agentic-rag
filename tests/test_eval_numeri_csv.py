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


def test_i_codici_conto_restano_testo(tmp_path) -> None:
    # "64.01" sembra un numero ma è un codice: le query attese lo confrontano come testo
    (tmp_path / "fatture_righe.csv").write_text(
        "id,categoria,imponibile\nR1,64.01,850.00\nR2,64.02,550.00\n", encoding="utf-8"
    )
    (tmp_path / "piano_dei_conti.csv").write_text(
        "codice,descrizione\n64.01,Alberghi\n64.02,Treni\n", encoding="utf-8"
    )
    q = esegui_query_attesa(
        "SELECT SUM(imponibile) FROM fatture_righe WHERE categoria IN ('64.01')", tmp_path
    )
    assert q is not None and q.valori == {D("850.0")}
    unite = esegui_query_attesa(
        "SELECT r.imponibile FROM fatture_righe r JOIN piano_dei_conti p ON r.categoria = p.codice",
        tmp_path,
    )
    assert unite is not None and unite.n_righe == 2
    # e il codice non finisce tra i numeri attesi
    solo_codice = esegui_query_attesa("SELECT categoria FROM fatture_righe", tmp_path)
    assert solo_codice is not None and solo_codice.valori == set()
