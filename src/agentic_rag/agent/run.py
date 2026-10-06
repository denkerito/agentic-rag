"""Esecuzione di un'indagine: connessione read-only, schema, limiti di utilizzo."""

import psycopg
from pydantic_ai import Agent
from pydantic_ai.usage import UsageLimits

from agentic_rag import config as app_config
from agentic_rag.agent import config
from agentic_rag.agent.agent import build_agent
from agentic_rag.agent.deps import AgentDeps, list_relations
from agentic_rag.agent.model import build_model
from agentic_rag.agent.output import Risposta
from agentic_rag.agent.schema_prompt import build_schema_ddl


def usage_limits() -> UsageLimits:
    return UsageLimits(request_limit=config.AGENT_MAX_REQUESTS)


def open_session(model: str | None = None) -> tuple[Agent[AgentDeps, Risposta], AgentDeps]:
    """Apre la connessione agent_ro e prepara agente e deps. Chi chiama chiude `deps.conn`."""
    if not app_config.DATABASE_URL_AGENT:
        raise SystemExit("DATABASE_URL_AGENT non impostata (vedi .env.example)")
    # autocommit: agent_ro ha idle_in_transaction_session_timeout=30s, e una transazione implicita
    # aperta da una query di setup o di ricerca verrebbe uccisa mentre si attende il modello.
    conn = psycopg.connect(app_config.DATABASE_URL_AGENT, autocommit=True)
    try:
        deps = AgentDeps(conn=conn, relations=list_relations(conn))
        agent = build_agent(build_model(model), schema=build_schema_ddl(conn))
    except BaseException:
        conn.close()
        raise
    return agent, deps


def investigate(domanda: str, model: str | None = None) -> tuple[Risposta, AgentDeps]:
    agent, deps = open_session(model)
    try:
        result = agent.run_sync(domanda, deps=deps, usage_limits=usage_limits())
        return result.output, deps
    finally:
        deps.conn.close()
