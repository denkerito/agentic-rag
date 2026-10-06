from pydantic_ai import Agent, ModelRetry, RunContext, Tool
from pydantic_ai.models import Model

from agentic_rag.agent.deps import AgentDeps
from agentic_rag.agent.model import build_model
from agentic_rag.agent.output import Risposta
from agentic_rag.agent.prompt import SYSTEM_PROMPT
from agentic_rag.agent.tools import apri_documento, cerca_documenti, query_sql

DOC_PREFIXES = ("DOC-", "CTR-")


def check_risposta(risposta: Risposta, seen_ids: set[str]) -> None:
    """Solleva ModelRetry se la risposta viola i vincoli sulle fonti."""
    cited = set(risposta.fonti) | {f for n in risposta.numeri for f in n.fonti}
    unseen = sorted(cited - seen_ids)
    if unseen:
        raise ModelRetry(
            f"Fonti mai ricevute dai tool: {', '.join(unseen)}. "
            "Cita solo ID comparsi nei risultati dei tool."
        )
    senza_fonti = [n.descrizione for n in risposta.numeri if not n.fonti]
    if senza_fonti:
        raise ModelRetry(f"Numeri senza fonti: {'; '.join(senza_fonti)}.")
    if risposta.causa_documentata and not any(f.startswith(DOC_PREFIXES) for f in cited):
        raise ModelRetry(
            "causa_documentata=true richiede almeno una fonte documentale (DOC-* o CTR-*)."
        )


def build_agent(model: Model | str | None = None, schema: str = "") -> Agent[AgentDeps, Risposta]:
    agent = Agent(
        model or build_model(),
        deps_type=AgentDeps,
        output_type=Risposta,
        instructions=SYSTEM_PROMPT.format(schema=schema),
        # sequential: i tool condividono una connessione psycopg e non devono sovrapporsi
        tools=[Tool(f, sequential=True) for f in (query_sql, cerca_documenti, apri_documento)],
        retries=3,
    )

    @agent.output_validator
    def _validate(ctx: RunContext[AgentDeps], output: Risposta) -> Risposta:
        check_risposta(output, ctx.deps.seen_ids)
        return output

    return agent
