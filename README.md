# agentic-rag

## Setup database

```bash
cp .env.example .env            # poi aggiorna le URL se cambi le password
docker compose up -d            # Postgres + pgvector
pip install -e ".[dev]"
python -m agentic_rag.db.init --reset
python -m agentic_rag.rag.indexer   # chunking + embedding (richiede GOOGLE_API_KEY)
```

Ruoli: `postgres` (solo bootstrap), `agentic_owner` (DDL e caricamento), `agent_ro` (sola lettura, usato dall'agente).
Test di integrazione: `pytest -m integration`.
