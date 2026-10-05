from typing import Literal

from pydantic import BaseModel, Field


class Numero(BaseModel):
    descrizione: str
    valore: str = Field(description="Valore esattamente come restituito da SQL, con unità")
    fonti: list[str] = Field(description="ID (FATT-*, MOV-*, SCR-*, ...) a supporto del numero")


class Risposta(BaseModel):
    conclusione: str
    numeri: list[Numero] = Field(default_factory=list)
    fonti: list[str] = Field(description="Tutti gli ID citati: devono provenire dai tool")
    confidenza: Literal["alta", "media", "bassa"]
    causa_documentata: bool = Field(
        description="True solo se un documento (DOC-*, CTR-*) supporta la causa indicata"
    )
    limiti: str | None = Field(
        default=None, description="Cosa non è documentato o non è stato verificato"
    )
