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

## Agente

```bash
python -m agentic_rag.agent "Perché il margine è diminuito ad agosto?"
```

Stampa i passi (query SQL, ricerche, documenti aperti) e la risposta con numeri e fonti.
Il modello è configurabile con `AGENT_MODEL` (default `google:gemini-3.5-flash-lite`, usa `GOOGLE_API_KEY`).
Le viste `v_economico*` e `v_margine_mensile` definiscono ricavi, costi e margine per competenza;
sono nello schema, quindi dopo averle aggiunte serve `python -m agentic_rag.db.init --reset`
(e di nuovo l'indexer, perché il reset svuota i chunk).
