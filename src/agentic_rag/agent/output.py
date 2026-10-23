from typing import Literal

from pydantic import BaseModel, Field


class Numero(BaseModel):
    descrizione: str
    valore: str = Field(description="Valore esattamente come restituito da SQL, con unità")
    fonti: list[str] = Field(description="ID (FATT-*, MOV-*, SCR-*, ...) a supporto del numero")


class Assenza(BaseModel):
    affermazione: str = Field(
        description="Cosa nei dati non esiste o non è accaduto, es. 'nessuna fattura pagata due volte'"
    )
    query_id: str = Field(
        description="ID della query (Q1, Q2...) che lo prova: risultato completo (non un'anteprima) "
        "e vuoto, oppure con soli conteggi a zero"
    )


class Risposta(BaseModel):
    conclusione: str
    numeri: list[Numero] = Field(default_factory=list)
    fonti: list[str] = Field(description="Tutti gli ID citati: devono provenire dai tool")
    confidenza: Literal["alta", "media", "bassa"] = Field(
        description="alta: numeri e cause verificati con le fonti; media: verifica parziale; "
        "bassa: dati insufficienti o domanda non rispondibile"
    )
    causa_documentata: bool = Field(
        description="True solo se un documento (DOC-*, CTR-*) supporta la causa indicata"
    )
    assenze: list[Assenza] = Field(
        default_factory=list,
        description="Ogni affermazione che qualcosa nei dati non esiste o non è accaduto, con la "
        "query che la prova",
    )
    limiti: str | None = Field(
        default=None, description="Cosa non è documentato o non è stato verificato"
    )
