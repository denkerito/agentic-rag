"""Esito per modalità e, soprattutto, test anti-leak: il report pubblico non contiene il ground truth."""

from datetime import UTC, datetime
from decimal import Decimal as D

import pytest

from agentic_rag.agent.output import Numero, Risposta
from agentic_rag.eval import report
from agentic_rag.eval.groundtruth import Domanda, Modalita
from agentic_rag.eval.numeri import RisultatoQuery
from agentic_rag.eval.runner import RisultatoDomanda
from agentic_rag.eval.valutazione import Giudizio, valuta

SEGRETI = {
    "domanda": "SEGRETO-DOMANDA-xyz",
    "tipo": "SEGRETO-TIPO-causa-una-tantum",
    "attesa": "SEGRETO-RISPOSTA-ATTESA",
    "id": "CTR-987",
    "numero": "123456.78",
    "motivazione": "SEGRETO-MOTIVAZIONE-GIUDICE",
}


def _domanda(tipo: str = "x", **kw) -> Domanda:
    base = {
        "id": 7,
        "domanda": SEGRETI["domanda"],
        "storia_id": "ZZ-03",
        "tipo": tipo,
        "risposta_attesa": SEGRETI["attesa"],
        "fonti_attese": [SEGRETI["id"], "fatture.csv"],
        "query_sql": "SELECT 1",
    }
    return Domanda.model_validate(base | kw)


def _risposta(**kw) -> Risposta:
    base = {
        "conclusione": "Conclusione dell'agente",
        "fonti": ["DOC-EML-001"],
        "numeri": [Numero(descrizione="x", valore="1,00", fonti=["DOC-EML-001"])],
        "confidenza": "alta",
        "causa_documentata": True,
        "limiti": None,
    }
    return Risposta.model_validate(base | kw)


TRACE = [{"kind": "sql", "sql": "SELECT * FROM fatture"}]


def test_normale_ok_quando_tutto_coincide() -> None:
    d = _domanda(fonti_attese=["CTR-001", "fatture.csv"])
    v = valuta(
        d,
        _risposta(fonti=["CTR-001"], numeri=[Numero(descrizione="n", valore="8", fonti=[])]),
        TRACE,
        {"CTR-001"},
        RisultatoQuery(valori={D(8)}, n_righe=1),
    )
    assert v.esito == "ok"


def test_normale_ko_se_manca_una_fonte() -> None:
    d = _domanda(fonti_attese=["CTR-001", "fatture.csv"], query_sql=None)
    assert valuta(d, _risposta(fonti=["DOC-EML-001"]), TRACE, {"DOC-EML-001"}, None).esito == "ko"


def test_onesta_guarda_il_comportamento_non_le_fonti() -> None:
    d = _domanda(tipo="risposta onesta: causa non documentata")
    assert d.modalita == Modalita.ONESTA
    bene = _risposta(causa_documentata=False, limiti="Causa non documentata")
    male = _risposta(causa_documentata=True, limiti=None)
    assert valuta(d, bene, TRACE, {"DOC-EML-001"}, None).esito == "ok"
    assert valuta(d, male, TRACE, {"DOC-EML-001"}, None).esito == "ko"


def test_non_rispondibile_richiede_prudenza_e_nessun_numero() -> None:
    d = _domanda(tipo="non rispondibile", fonti_attese=[])
    prudente = _risposta(
        causa_documentata=False, limiti="Dati assenti", confidenza="bassa", numeri=[]
    )
    assert valuta(d, prudente, [], set(), None).esito == "ok"
    sicuro = _risposta(causa_documentata=False, limiti="x", confidenza="alta", numeri=[])
    assert valuta(d, sicuro, [], set(), None).esito == "ko"
    inventa = _risposta(causa_documentata=False, limiti="x", confidenza="bassa")
    assert valuta(d, inventa, [], set(), None).esito == "ko"


def test_senza_controlli_applicabili_e_nd_e_il_giudice_lo_decide() -> None:
    d = _domanda(fonti_attese=[], query_sql=None)
    r = _risposta()
    assert valuta(d, r, [], set(), None).esito == "nd"
    assert (
        valuta(d, r, [], set(), None, Giudizio(verdetto="corretta", motivazione="m")).esito == "ok"
    )
    assert valuta(d, r, [], set(), None, Giudizio(verdetto="errata", motivazione="m")).esito == "ko"
    assert (
        valuta(d, r, [], set(), None, Giudizio(verdetto="parziale", motivazione="m")).esito == "ok"
    )


def _risultato() -> RisultatoDomanda:
    d = _domanda(tipo=SEGRETI["tipo"], query_sql="SELECT 1")
    r = _risposta()
    v = valuta(
        d,
        r,
        TRACE,
        {"DOC-EML-001"},
        RisultatoQuery(valori={D(SEGRETI["numero"])}, n_righe=1),
        Giudizio(verdetto="parziale", motivazione=SEGRETI["motivazione"]),
    )
    return RisultatoDomanda(
        domanda=d,
        esito=v.esito,
        risposta=r,
        valutazione=v,
        sql_agente=["SELECT * FROM fatture"],
        tabelle_lette=["fatture"],
        richieste=7,
        durata_s=12.3,
    )


def test_anti_leak_il_report_pubblico_non_contiene_il_ground_truth(tmp_path) -> None:
    percorsi, console = report.scrivi(
        [_risultato()],
        {"modello": "test"},
        tmp_path,
        adesso=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
    )
    pubblico = "\n".join(
        [
            percorsi["pubblico_json"].read_text(encoding="utf-8"),
            percorsi["pubblico_md"].read_text(encoding="utf-8"),
        ]
        + console
    )
    for nome, segreto in SEGRETI.items():
        assert segreto not in pubblico, f"il report pubblico espone '{nome}'"
    # ma il pubblico è utile: conteggi, esito, risposta dell'agente
    assert "Conclusione dell'agente" in pubblico and "0/1" in pubblico and "parziale" in pubblico


def test_il_report_privato_contiene_le_attese(tmp_path) -> None:
    percorsi, _ = report.scrivi(
        [_risultato()], {}, tmp_path, adesso=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    )
    privato = percorsi["privato_json"].read_text(encoding="utf-8") + percorsi[
        "privato_md"
    ].read_text(encoding="utf-8")
    for nome, segreto in SEGRETI.items():
        assert segreto in privato, f"il report privato non ha '{nome}'"
    assert percorsi["privato_json"].parent.name == report.PRIVATE_SUBDIR


def test_aggregati_per_storia_e_modalita() -> None:
    a = _risultato()
    a.esito = "ok"
    b = _risultato()
    b.esito = "ko"
    b.domanda = _domanda(id=8, storia_id="generale", tipo="non rispondibile")
    agg = report.aggregati([a, b])
    assert agg["totale"]["domande"] == 2 and agg["totale"]["ko"] == 1
    assert set(agg["per_storia"]) == {"ZZ-03", "-"}
    assert set(agg["per_modalita"]) == {"normale", "non_rispondibile"}


@pytest.mark.parametrize("esito", ["errore"])
def test_domanda_in_errore_e_riportata_senza_dettagli_del_ground_truth(esito, tmp_path) -> None:
    r = RisultatoDomanda(domanda=_domanda(), esito=esito, errore="ModelHTTPError")
    percorsi, _ = report.scrivi([r], {}, tmp_path, adesso=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC))
    pubblico = percorsi["pubblico_md"].read_text(encoding="utf-8")
    assert "ModelHTTPError" in pubblico and SEGRETI["attesa"] not in pubblico
