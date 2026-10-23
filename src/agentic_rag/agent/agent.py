from typing import Any

from pydantic_ai import Agent, ModelRetry, RunContext, Tool
from pydantic_ai.models import Model

from agentic_rag.agent.deps import AgentDeps
from agentic_rag.agent.model import build_model
from agentic_rag.agent.output import Risposta
from agentic_rag.agent.prompt import SYSTEM_PROMPT
from agentic_rag.agent.tools import (
    apri_documento,
    cerca_semantica,
    cerca_testo,
    elenca_documenti,
    query_sql,
)

DOC_PREFIXES = ("DOC-", "CTR-")
# Inizio dei messaggi di rifiuto del validatore: l'eval li usa per contare i rifiuti per motivo.
RIFIUTO_FONTI_NON_VISTE = "Fonti mai ricevute dai tool"
RIFIUTO_NUMERI_SENZA_FONTI = "Numeri senza fonti"
RIFIUTO_CAUSA_SENZA_DOCUMENTO = "causa_documentata=true richiede"
RIFIUTO_CAUSA_NON_LETTA = "Causa documentata senza documenti aperti"
RIFIUTO_ASSENZA_NON_PROVATA = "Assenza non provata"
# Nessun prefisso deve iniziare con un altro: ogni rifiuto si conta per un solo motivo.
MOTIVI_RIFIUTO: dict[str, str] = {
    "fonti_non_viste": RIFIUTO_FONTI_NON_VISTE,
    "numeri_senza_fonti": RIFIUTO_NUMERI_SENZA_FONTI,
    "causa_senza_documento": RIFIUTO_CAUSA_SENZA_DOCUMENTO,
    "causa_non_letta": RIFIUTO_CAUSA_NON_LETTA,
    "assenza_non_provata": RIFIUTO_ASSENZA_NON_PROVATA,
}


def check_risposta(
    risposta: Risposta,
    seen_ids: set[str],
    aperti: set[str],
    query: dict[str, dict[str, Any]] | None = None,
) -> None:
    """Solleva ModelRetry se la risposta viola i vincoli sulle fonti.

    Un documento trovato da una ricerca è citabile, ma come causa conta solo se aperto: i frammenti
    di una ricerca dicono dove guardare, non provano la causa.
    """
    cited = set(risposta.fonti) | {f for n in risposta.numeri for f in n.fonti}
    unseen = sorted(cited - seen_ids)
    if unseen:
        raise ModelRetry(
            f"{RIFIUTO_FONTI_NON_VISTE}: {', '.join(unseen)}. "
            "Cita solo ID comparsi nei risultati dei tool."
        )
    senza_fonti = [n.descrizione for n in risposta.numeri if not n.fonti]
    if senza_fonti:
        raise ModelRetry(f"{RIFIUTO_NUMERI_SENZA_FONTI}: {'; '.join(senza_fonti)}.")
    if risposta.causa_documentata and not any(f.startswith(DOC_PREFIXES) for f in cited):
        raise ModelRetry(
            f"{RIFIUTO_CAUSA_SENZA_DOCUMENTO} almeno una fonte documentale (DOC-* o CTR-*)."
        )
    documenti = sorted(f for f in cited if f.startswith(DOC_PREFIXES))
    if risposta.causa_documentata and not aperti.intersection(documenti):
        raise ModelRetry(
            f"{RIFIUTO_CAUSA_NON_LETTA}: apri con apri_documento almeno uno tra "
            f"{', '.join(documenti)} prima di dichiarare la causa documentata, "
            "oppure usa causa_documentata=false."
        )
    for a in risposta.assenze:
        q = (query or {}).get(a.query_id)
        if q is None:
            motivo = (
                f"la query {a.query_id} è inesistente: cita il query_id restituito da query_sql"
            )
        elif not q["completo"]:
            motivo = f"{a.query_id} è un'anteprima, non il risultato completo: aggrega o filtra"
        elif not q["zero"]:
            motivo = (
                f"{a.query_id} restituisce righe: filtra con HAVING o WHERE finché il risultato è "
                "vuoto o a zero, oppure togli l'assenza"
            )
        else:
            continue
        raise ModelRetry(f"{RIFIUTO_ASSENZA_NON_PROVATA} ({a.affermazione!r}): {motivo}.")


def build_agent(
    model: Model | str | None = None, schema: str = "", ricerca_semantica: bool = True
) -> Agent[AgentDeps, Risposta]:
    # senza ricerca semantica (ablazione) cambia solo l'elenco dei tool: il prompt non li nomina
    funzioni = [query_sql, elenca_documenti, cerca_testo]
    if ricerca_semantica:
        funzioni.append(cerca_semantica)
    funzioni.append(apri_documento)
    agent = Agent(
        model or build_model(),
        deps_type=AgentDeps,
        output_type=Risposta,
        instructions=SYSTEM_PROMPT.format(schema=schema),
        # sequential: i tool condividono una connessione psycopg e non devono sovrapporsi
        tools=[Tool(f, sequential=True) for f in funzioni],
        retries=3,
    )

    @agent.output_validator
    def _validate(ctx: RunContext[AgentDeps], output: Risposta) -> Risposta:
        check_risposta(output, ctx.deps.seen_ids, ctx.deps.aperti, ctx.deps.query)
        return output

    return agent
