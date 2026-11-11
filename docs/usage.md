# Reference

Everything the [README](../README.md) leaves out: running the project, the command line, the API, configuration and evaluation. The code, the agent's prompt and the data are in Italian, so commands, flags and API paths use Italian names.

## Running locally

Setup is in the README's quick start. Without containers:

```bash
uvicorn agentic_rag.api.app:app          # a single worker: investigations live in the process
cd frontend && npm install && npm run dev
```

From the command line (the agent works in Italian):

```bash
python -m agentic_rag.agent "Perché il margine è diminuito ad agosto?"
```

## Agent tools

| Tool | What it does |
|---|---|
| `query_sql` | read-only SQL: metrics, period comparisons, invoices and payments |
| `elenca_documenti` | lists documents by type, period, customer or supplier |
| `cerca_testo` | Italian full-text search over title and content |
| `cerca_semantica` | search by meaning (pgvector); always on in the product |
| `apri_documento` | reads a whole document |

The design of the document tools is in [this spec](superpowers/specs/2026-10-16-ricerca-documenti-opzione-a-design.md).

## Database roles

- `postgres`: bootstrap only.
- `agentic_owner`: DDL and data loading.
- `agent_ro`: read-only, used by the agent (10 s statement timeout, read-only transactions).
- `app_rw`: writes the investigation history in the `app` schema, with no access to the accounting data.

On an already initialised database, `python -m agentic_rag.db.init` accepts `--app-only` (history), `--fulltext-only` (document full-text search) and `--views-only` (financial views), without touching data and embeddings.

## Environment variables

Main ones: `OPENROUTER_API_KEY`, `GOOGLE_API_KEY`, `AGENT_MODEL` (default `openrouter:anthropic/claude-haiku-5.5`), `JUDGE_MODEL` (default `openrouter:anthropic/claude-sonnet-5.5`), `AGENT_MAX_REQUESTS` (25), `DATABASE_URL*`, `CORS_ORIGINS`, `MAX_INDAGINI_CONCORRENTI` (3), `LOGFIRE_TOKEN`. Optional per-minute limits: `AGENT_RPM`, `AGENT_TPM`, `JUDGE_RPM`, `JUDGE_TPM`. See `.env.example`.

With Docker the API reaches the database as `db` (`DATABASE_URL_APP_DOCKER` / `DATABASE_URL_AGENT_DOCKER`, needed only if you changed the passwords).

## API

| Endpoint | |
|---|---|
| `POST /indagini` `{"domanda": "..."}` | starts an investigation, `202 {id, stato}` |
| `GET /indagini?limit&before` | list |
| `GET /indagini/{id}` | status, answer, error, usage |
| `GET /indagini/{id}/eventi` | server-sent events: replay + live tail (`Last-Event-ID` / `?dopo=<seq>`) |
| `POST /indagini/{id}/stop` | stops the investigation |
| `GET /fonti/{id}` | opens a cited source (fields, linked tables, text), read-only |

Events: `tool_call`, `tool_result` (counts and IDs only, never rows), `tool_retry`, `risposta_scartata`, and the final `risposta`, `errore` or `interrotta`. An investigation keeps running if the page is closed; after a server restart, the ones in progress become `interrotta`.

## Tests

```bash
pytest                       # unit tests
pytest -m integration        # needs the database and the index; about 6 Gemini calls per run
cd frontend && npm test && npm run build
```

## Evaluation

The harness runs questions through the same agent as the API and compares the answers with a ground truth: the sources a correct investigation must cite, an SQL query whose values are the expected numbers, and the expected behaviour when the cause is undocumented or the question cannot be answered.

- **Development set** (`eval/ground_truth/`): 12 questions, used to tune agent, validator and harness.
- **Test set** (`eval/ground_truth_finale/`): 50 questions, hidden from development until the `finale` experiment ended. It is no longer unseen: a future change to the agent needs a new test set.

```bash
python -m agentic_rag.eval --dry-run            # checks the ground truth, no model calls
python -m agentic_rag.eval --ids 1,4 --judge    # some questions, with the LLM judge

# experiments: variants × repetitions × questions, resumable
python -m agentic_rag.eval.esperimento esegui --etichetta esp --variante haiku --ripetizioni 3 --judge
python -m agentic_rag.eval.esperimento esegui --etichetta esp                  # resume
python -m agentic_rag.eval.esperimento riepilogo --etichetta esp               # summary
python -m agentic_rag.eval.esperimento etichette --etichetta esp --campione 30 # sheet for human labels
python -m agentic_rag.eval.esperimento kappa --etichetta esp                   # human/judge agreement
python tools/etichetta_giudice.py --etichetta esp                              # label in the terminal

# retrieval benchmark: precision@k, recall@k, MRR
python -m agentic_rag.eval.recupero --gt eval/ground_truth_finale --nome finale
```

How experiments behave:
- each run is saved as soon as it ends; a manifest ties the experiment to the code and to the ground truth hash, and a resume is refused if they changed;
- network and provider errors (429, 5xx) are retried and never count as agent failures; exhausted credit or an invalid key (401/402/403) stops the run, which can be resumed;
- the 300 s timeout counts working time only, and hitting it is an agent failure;
- comparisons use only combinations completed in every variant; above 10% excluded, the experiment is declared invalid.

Metrics (95% CI, bootstrap over questions): task success rate, answer accuracy (LLM judge, checked with Cohen's κ), pass^3, source citation recall, numeric exact match recall, false acceptance and false abstention rates, guardrail intervention rate, session evidence recall, plus tokens, cost and latency. Definitions are in the [harness design](superpowers/specs/2026-10-19-harness-esperimenti-design.md); the full story of the final experiment, including the post-experiment analysis, is in [this spec](superpowers/specs/2026-10-21-percorso-valutazione-openrouter-design.md).

Public reports are in `eval/reports/`; private reports (with the ground truth) go to `eval/reports/private/`, which is git-ignored.
