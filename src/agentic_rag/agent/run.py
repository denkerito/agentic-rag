"""Esecuzione di un'indagine: connessione read-only, schema, limiti di utilizzo, retry sui 429."""

import time

import psycopg
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.usage import UsageLimits

from agentic_rag import config as app_config
from agentic_rag.agent import config
from agentic_rag.agent.agent import build_agent
from agentic_rag.agent.deps import AgentDeps, list_relations
from agentic_rag.agent.output import Risposta
from agentic_rag.agent.schema_prompt import build_schema_ddl

MAX_429_RETRIES = 4


def investigate(domanda: str, model: str | None = None) -> tuple[Risposta, AgentDeps]:
    if not app_config.DATABASE_URL_AGENT:
        raise SystemExit("DATABASE_URL_AGENT non impostata (vedi .env.example)")
    with psycopg.connect(app_config.DATABASE_URL_AGENT) as conn:
        deps = AgentDeps(conn=conn, relations=list_relations(conn))
        agent = build_agent(model, schema=build_schema_ddl(conn))
        for attempt in range(MAX_429_RETRIES + 1):
            try:
                result = agent.run_sync(
                    domanda,
                    deps=deps,
                    usage_limits=UsageLimits(request_limit=config.AGENT_MAX_REQUESTS),
                )
                return result.output, deps
            except ModelHTTPError as e:
                if e.status_code != 429 or attempt == MAX_429_RETRIES:
                    raise
                time.sleep(min(60, 10 * 2**attempt))
    raise AssertionError("unreachable")
