# agentic-rag

## Setup database

```bash
cp .env.example .env            # poi aggiorna le URL se cambi le password
docker compose up -d            # Postgres + pgvector
pip install -e ".[dev]"
python -m agentic_rag.db.init --reset
python -m agentic_rag.rag.indexer   # chunking + embedding (richiede GOOGLE_API_KEY)
```

Ruoli: `postgres` (solo bootstrap), `agentic_owner` (DDL e caricamento), `agent_ro` (sola lettura, usato dall'agente),
`app_rw` (scrive lo storico delle indagini nello schema `app`, senza accesso a `public`).
Su un database già inizializzato, per aggiungere solo ruolo e schema `app` (senza toccare dati ed embedding):
`python -m agentic_rag.db.init --app-only` (richiede `DATABASE_URL_APP` nel `.env`).
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

## API (indagini in background + streaming dei passi)

```bash
uvicorn agentic_rag.api.app:app      # un solo worker: le indagini vivono nel processo
```

Un'indagine continua anche se si chiude la pagina; passi e risposta sono salvati nello schema `app`
e si possono rivedere. L'unico intervento possibile è fermarla.

| Endpoint | |
|---|---|
| `POST /indagini` `{"domanda": "..."}` | avvia, `202 {id, stato}` |
| `GET /indagini?limit&before` | elenco |
| `GET /indagini/{id}` | stato, risposta, errore, utilizzo |
| `GET /indagini/{id}/eventi` | SSE: replay + coda live, si chiude dopo l'evento terminale |
| `POST /indagini/{id}/stop` | ferma (409 se non è in corso) |

Eventi SSE (`event:` = tipo, `id:` = seq, `data:` = JSON). Riconnessione con `Last-Event-ID` o `?dopo=<seq>`.

| tipo | contenuto |
|---|---|
| `tool_call` | tool e argomenti (per `query_sql` la SQL) |
| `tool_result` | conteggi e ID fonte (`ids`, `n_righe`, `n_pertinenti`, ...), mai le righe |
| `tool_retry` | il tool ha rifiutato la chiamata (SQL non valida, ...) |
| `risposta_scartata` | il validator ha rifiutato la risposta (fonti mai viste, ...) |
| `risposta` *(terminale)* | `Risposta` validata |
| `errore` *(terminale)* | `errore`, `messaggio` |
| `interrotta` *(terminale)* | stop dell'utente o riavvio del server |

```bash
curl -N localhost:8000/indagini/<id>/eventi
```

Con un server riavviato le indagini in corso vengono marcate `interrotta`. Variabili: `DATABASE_URL_APP`,
`CORS_ORIGINS` (default `http://localhost:5173`), `MAX_INDAGINI_CONCORRENTI` (default 3).
