import time

from agentic_rag.eval.ambiente import controlla_ambiente


def test_database_irraggiungibile_e_chiave_mancante_sono_segnalati_subito() -> None:
    t = time.monotonic()
    problemi = controlla_ambiente(db_url="postgresql://u:p@127.0.0.1:1/db", api_key="")
    assert time.monotonic() - t < 15  # nessuna attesa di minuti
    assert any("database non risponde" in p and "docker compose up -d db" in p for p in problemi)
    assert any("GOOGLE_API_KEY" in p for p in problemi)


def test_configurazione_assente() -> None:
    problemi = controlla_ambiente(db_url="", api_key="k")
    assert problemi == ["DATABASE_URL_AGENT non impostata nel .env"]
