"""GET /fonti/{id}: risolve un ID di fonte (FATT-*, MOV-*, CTR-*, ...) nel record che lo documenta.

Sola lettura col ruolo agent_ro. I collegamenti (altri ID citati nel record) permettono di
navigare fattura -> movimento -> scrittura.
"""

import asyncio
from typing import Any, Literal

import psycopg
from fastapi import APIRouter, HTTPException
from psycopg.rows import dict_row
from pydantic import BaseModel

from agentic_rag import config
from agentic_rag.agent.ids import ID_PATTERN, extract_ids

router = APIRouter(prefix="/fonti", tags=["fonti"])

Row = dict[str, Any]
Conn = psycopg.Connection[Row]
TipoFonte = Literal[
    "fattura",
    "riga_fattura",
    "movimento",
    "scrittura",
    "scadenza",
    "contratto",
    "documento",
    "cliente",
    "fornitore",
]


class Campo(BaseModel):
    nome: str
    valore: str | None


class Tabella(BaseModel):
    titolo: str
    colonne: list[str]
    righe: list[list[str | None]]


class Fonte(BaseModel):
    id: str
    tipo: TipoFonte
    titolo: str
    campi: list[Campo]
    tabelle: list[Tabella] = []
    testo: str | None = None
    collegamenti: list[str] = []


def _s(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "sì" if value else "no"
    return str(value)


def _campi(row: Row, escludi: tuple[str, ...] = ()) -> list[Campo]:
    return [Campo(nome=k, valore=_s(v)) for k, v in row.items() if k not in escludi]


def _tabella(titolo: str, rows: list[Row]) -> list[Tabella]:
    if not rows:
        return []
    colonne = list(rows[0])
    return [
        Tabella(titolo=titolo, colonne=colonne, righe=[[_s(r[c]) for c in colonne] for r in rows])
    ]


def _controparte(conn: Conn, cliente_id: str | None, fornitore_id: str | None) -> Campo | None:
    if cliente_id:
        sql, key, nome = "SELECT denominazione FROM clienti WHERE id = %s", cliente_id, "cliente"
    elif fornitore_id:
        sql, key, nome = (
            "SELECT denominazione FROM fornitori WHERE id = %s",
            fornitore_id,
            "fornitore",
        )
    else:
        return None
    row = conn.execute(sql, (key,)).fetchone()
    return Campo(nome=f"{nome}_denominazione", valore=row["denominazione"] if row else None)


def _aggiungi(campi: list[Campo], extra: Campo | None) -> list[Campo]:
    return campi + [extra] if extra else campi


def _fattura(conn: Conn, id: str) -> Fonte | None:
    f = conn.execute("SELECT * FROM fatture WHERE id = %s", (id,)).fetchone()
    if f is None:
        return None
    campi = _aggiungi(_campi(f), _controparte(conn, f["cliente_id"], f["fornitore_id"]))
    tabelle = (
        _tabella(
            "Righe",
            conn.execute(
                "SELECT id, riga_numero, descrizione, conto_codice, quantita, prezzo, imponibile "
                "FROM fatture_righe WHERE fattura_id = %s ORDER BY riga_numero",
                (id,),
            ).fetchall(),
        )
        + _tabella(
            "Movimenti bancari collegati",
            conn.execute(
                "SELECT id, data, importo, causale FROM movimenti_bancari "
                "WHERE fattura_id = %s ORDER BY data, id",
                (id,),
            ).fetchall(),
        )
        + _tabella(
            "Scritture contabili",
            conn.execute(
                "SELECT id, data, conto_codice, dare, avere FROM scritture_contabili "
                "WHERE fattura_id = %s ORDER BY id",
                (id,),
            ).fetchall(),
        )
    )
    return Fonte(
        id=id,
        tipo="fattura",
        titolo=f"Fattura {f['tipo']} n. {f['numero']}",
        campi=campi,
        tabelle=tabelle,
    )


def _riga(conn: Conn, id: str) -> Fonte | None:
    r = conn.execute(
        "SELECT r.*, p.descrizione AS conto_descrizione FROM fatture_righe r "
        "JOIN piano_dei_conti p ON p.codice = r.conto_codice WHERE r.id = %s",
        (id,),
    ).fetchone()
    if r is None:
        return None
    return Fonte(
        id=id,
        tipo="riga_fattura",
        titolo=f"Riga {r['riga_numero']} della fattura {r['fattura_id']}",
        campi=_campi(r),
    )


def _movimento(conn: Conn, id: str) -> Fonte | None:
    m = conn.execute("SELECT * FROM movimenti_bancari WHERE id = %s", (id,)).fetchone()
    if m is None:
        return None
    scritture = conn.execute(
        "SELECT id, data, conto_codice, dare, avere FROM scritture_contabili "
        "WHERE movimento_id = %s ORDER BY id",
        (id,),
    ).fetchall()
    return Fonte(
        id=id,
        tipo="movimento",
        titolo=f"Movimento bancario del {m['data']}",
        campi=_campi(m),
        tabelle=_tabella("Scritture contabili", scritture),
    )


def _scrittura(conn: Conn, id: str) -> Fonte | None:
    s = conn.execute(
        "SELECT s.*, p.descrizione AS conto_descrizione FROM scritture_contabili s "
        "JOIN piano_dei_conti p ON p.codice = s.conto_codice WHERE s.id = %s",
        (id,),
    ).fetchone()
    if s is None:
        return None
    stesse = conn.execute(
        "SELECT id, conto_codice, dare, avere FROM scritture_contabili "
        "WHERE transazione_id = %s ORDER BY id",
        (s["transazione_id"],),
    ).fetchall()
    return Fonte(
        id=id,
        tipo="scrittura",
        titolo=f"Scrittura contabile del {s['data']}",
        campi=_campi(s),
        tabelle=_tabella("Scritture della stessa transazione", stesse),
    )


def _scadenza(conn: Conn, id: str) -> Fonte | None:
    s = conn.execute("SELECT * FROM scadenzario WHERE id = %s", (id,)).fetchone()
    if s is None:
        return None
    campi = _aggiungi(_campi(s), _controparte(conn, s["cliente_id"], s["fornitore_id"]))
    return Fonte(id=id, tipo="scadenza", titolo=f"Scadenza del {s['data']}", campi=campi)


def _contratto(conn: Conn, id: str) -> Fonte | None:
    c = conn.execute("SELECT * FROM contratti WHERE id = %s", (id,)).fetchone()
    if c is None:
        return None
    doc = conn.execute("SELECT contenuto FROM documenti WHERE doc_id = %s", (id,)).fetchone()
    campi = _aggiungi(_campi(c), _controparte(conn, c["cliente_id"], c["fornitore_id"]))
    return Fonte(
        id=id,
        tipo="contratto",
        titolo=f"Contratto {c['tipo']}: {c['oggetto']}",
        campi=campi,
        testo=doc["contenuto"] if doc else None,
    )


def _documento(conn: Conn, id: str) -> Fonte | None:
    d = conn.execute("SELECT * FROM documenti WHERE doc_id = %s", (id,)).fetchone()
    if d is None:
        return None
    campi = _aggiungi(
        _campi(d, escludi=("contenuto",)), _controparte(conn, d["cliente_id"], d["fornitore_id"])
    )
    return Fonte(id=id, tipo="documento", titolo=d["titolo"], campi=campi, testo=d["contenuto"])


def _anagrafica(tabella: str, tipo: TipoFonte):
    def risolvi(conn: Conn, id: str) -> Fonte | None:
        row = conn.execute(f"SELECT * FROM {tabella} WHERE id = %s", (id,)).fetchone()
        if row is None:
            return None
        return Fonte(id=id, tipo=tipo, titolo=row["denominazione"], campi=_campi(row))

    return risolvi


RESOLVER = {
    "FATT": _fattura,
    "RIG": _riga,
    "MOV": _movimento,
    "SCR": _scrittura,
    "SCD": _scadenza,
    "CTR": _contratto,
    "DOC": _documento,
    "CLI": _anagrafica("clienti", "cliente"),
    "FOR": _anagrafica("fornitori", "fornitore"),
}


def risolvi(conn: Conn, id: str) -> Fonte | None:
    if not ID_PATTERN.fullmatch(id):
        return None
    fonte = RESOLVER[id.split("-", 1)[0]](conn, id)
    if fonte is not None:
        collegati = extract_ids(f"{fonte.campi} {fonte.tabelle}") - {id}
        fonte.collegamenti = sorted(collegati)
    return fonte


def _leggi(id: str) -> Fonte | None:
    with psycopg.connect(config.DATABASE_URL_AGENT, autocommit=True, row_factory=dict_row) as conn:
        return risolvi(conn, id)


@router.get("/{id}")
async def fonte(id: str) -> Fonte:
    result = await asyncio.to_thread(_leggi, id)
    if result is None:
        raise HTTPException(404, "Fonte inesistente")
    return result
