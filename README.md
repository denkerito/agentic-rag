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
| `GET /fonti/{id}` | apre una fonte citata (`FATT-*`, `MOV-*`, `SCR-*`, `RIG-*`, `SCD-*`, `CTR-*`, `DOC-*`, `CLI-*`, `FOR-*`): campi, tabelle collegate, testo, `collegamenti` ad altri ID (sola lettura, ruolo `agent_ro`) |

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

## Frontend (React)

```bash
docker compose up            # DB + API (http://localhost:8000) + UI (http://localhost:5173)
```

Ambiente di sviluppo con hot-reload: `src/` e `frontend/` sono montati nei container, quindi salvando un
file API e UI si aggiornano da soli (un riavvio dell'API interrompe le indagini in corso).
`docker compose up --build` dopo aver cambiato le dipendenze; porte con `API_PORT` / `UI_PORT`.
Il container dell'API usa `.env` (`GOOGLE_API_KEY`, `AGENT_MODEL`, ...) ma raggiunge il database come
`db`: gli URL `DATABASE_URL_APP_DOCKER` / `DATABASE_URL_AGENT_DOCKER` hanno per default le password di
`.env.example`, da impostare solo se le hai cambiate. Il database va inizializzato una volta dall'host
(sezione "Setup database": `python -m agentic_rag.db.init --reset`, oppure `--app-only` se esiste già).

Senza container, a mano: `uvicorn agentic_rag.api.app:app` e `cd frontend && npm install && npm run dev`.

Vite inoltra `/api/*` all'API (stesso origin, niente CORS); `VITE_API_BASE` cambia la base.
La UI mostra la nuova indagine, i passi in tempo reale (SQL, ricerche, risposte scartate dal controllo
sulle fonti), la risposta con confidenza, limiti e fonti cliccabili (pannello con la fattura, il
movimento, il documento, ... e i collegamenti tra fonti), lo storico e il pulsante **Ferma**.
Lo stream usa `EventSource` nativo: riconnette da solo riprendendo da `Last-Event-ID`.
Test: `npm test`; build con type-check: `npm run build`.
