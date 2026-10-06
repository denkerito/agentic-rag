import pytest
from fastapi.testclient import TestClient

from agentic_rag.api.app import create_app

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app()) as c:
        yield c


@pytest.mark.parametrize(
    ("id", "tipo"),
    [
        ("FATT-A-2025-0001", "fattura"),
        ("RIG-0001", "riga_fattura"),
        ("MOV-000001", "movimento"),
        ("SCR-000001", "scrittura"),
        ("SCD-0001", "scadenza"),
        ("CTR-001", "contratto"),
        ("DOC-EML-003", "documento"),
        ("CLI-001", "cliente"),
        ("FOR-001", "fornitore"),
    ],
)
def test_ogni_prefisso_si_risolve(client, id, tipo) -> None:
    r = client.get(f"/fonti/{id}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == id and body["tipo"] == tipo and body["titolo"] and body["campi"]
    assert id not in body["collegamenti"]


def test_fattura_ha_righe_controparte_e_collegamenti(client) -> None:
    body = client.get("/fonti/FATT-A-2025-0001").json()
    campi = {c["nome"]: c["valore"] for c in body["campi"]}
    assert campi["totale"] == "34160.00" and "Barilli" in campi["cliente_denominazione"]
    tabelle = {t["titolo"]: t for t in body["tabelle"]}
    assert "RIG-0001" in {r[0] for r in tabelle["Righe"]["righe"]}
    assert "RIG-0001" in body["collegamenti"]


def test_movimento_collega_la_fattura(client) -> None:
    assert "FATT-P-2025-0074" in client.get("/fonti/MOV-000001").json()["collegamenti"]


def test_booleani_in_italiano(client) -> None:
    campi = {c["nome"]: c["valore"] for c in client.get("/fonti/CTR-001").json()["campi"]}
    assert campi["rinnovo"] in ("sì", "no")


def test_contratto_e_documento_hanno_il_testo(client) -> None:
    assert client.get("/fonti/CTR-001").json()["testo"]
    doc = client.get("/fonti/DOC-EML-003").json()
    assert doc["testo"] and all(c["nome"] != "contenuto" for c in doc["campi"])


@pytest.mark.parametrize("id", ["FATT-A-2099-0001", "RIG-9999", "pippo", "FATT-1"])
def test_inesistente_o_malformato_e_404(client, id) -> None:
    assert client.get(f"/fonti/{id}").status_code == 404
