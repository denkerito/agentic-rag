# Document search: metadata browsing + full-text + semantic (option A)

Status: approved · 2026-10-16

## Why

Today the agent finds documents through a single channel: vector search (`cerca_documenti`) with a fixed cosine
distance threshold (0.38, calibrated by hand). Two consequences:

- **A negative result cannot be proven.** "No chunk under the threshold" is a statement about the threshold, not
  about the documents. The very case where the project promises honesty ("the cause is not documented") rests on the
  least verifiable channel.
- **Weak on exact terms** (names, codes, amounts), and no way for the agent to say "I looked at all of this
  supplier's documents in this period".

Option A gives the agent simple, deterministic search tools and leaves the strategy to it, in line with the
project's thesis ("the agent decides the path based on what it uncovers"). Semantic search stays as a channel for
paraphrases; a later experiment decides whether to keep it.

## Goals

1. The agent can **list documents by metadata** (type, period, customer, supplier), with no thresholds.
2. The agent can **search for words in the text** (Italian full-text, with stemming), with a binary result:
   a document either contains the terms or it does not.
3. **Semantic search** stays available as a separate tool and **can be switched off by configuration**, without
   changing the prompt or other tools, for the ablation.
4. The architecture is **credible with thousands of documents**: real indexes, paginated or limited results, never
   full texts in bulk in the context.
5. Every search is a **distinct, readable step** in the UI and in the history.
6. An **experiment with a criterion set in advance** decides whether the vectors stay.

## Non-goals

- Hybrid search with fusion (RRF) or a re-ranker: considered and dropped for this iteration (see "Alternatives").
- Structured extraction of documents with an LLM at ingestion: excluded (it would put LLM-generated data in the DB).
- A document index in the prompt: it does not scale.
- Changes to `query_sql`, the views, the source validator, the runner, authentication.
- A validator constraint "`causa_documentata=false` requires at least one full-text search": a possible next step,
  not in this iteration.

## Anti-goals (failure even if it works)

- Tuning the prompt, docstrings or thresholds **after** seeing the eval results to make questions pass
  (forbidden by `AGENTS.md`).
- A "no vectors" variant penalised by details of the harness rather than by the quality of the answers.
- A prompt that names the search tools: it would turn the ablation into a change of two variables.

## Constraints

- Default model unchanged (`AGENT_MODEL`, today `google:gemini-3.5-flash-lite`); the design works with any
  configured model.
- Everything in the existing PostgreSQL 17 + pgvector; no new infrastructure.
- The `agent_ro` role stays the only one the agent reads data with.
- The ground truth in `eval/ground_truth/` is not opened by whoever develops the agent (see `AGENTS.md`).

## Design

### Agent tools

| Tool | Status | Role |
|---|---|---|
| `query_sql` | unchanged | numbers |
| `elenca_documenti` | **new** | document index by metadata, paginated |
| `cerca_testo` | **new** | Italian full-text over title and content |
| `cerca_semantica` | **renamed** from `cerca_documenti`, same logic | paraphrases; can be switched off |
| `apri_documento` | unchanged | reads the document |

**`elenca_documenti(tipo?, data_da?, data_a?, cliente_id?, fornitore_id?, pagina=1)`**
- Returns `totale`, `pagina`, `pagine` and, for each document: `doc_id`, `tipo`, `data`, `titolo`,
  `cliente_id`/`fornitore_id` with the counterparty's name. No text.
- 30 documents per page, ordered by date (then `doc_id`).
- Does **not** add the IDs to `seen_ids`: a document seen only by title cannot be cited. It becomes citable when it
  is opened or appears in a search together with its text. As a **cause** (`causa_documentata=true`), on the other
  hand, only a document cited and **opened** with `apri_documento` counts: a snippet found by words (or by semantic
  proximity) tells you where to look, it does not prove the cause. The rule is the same for both searches, so the
  ablation with and without semantic search gives no shortcut to just one variant (rejection reason
  `causa_non_letta`).

**`cerca_testo(query, tipo?, data_da?, data_a?, cliente_id?, fornitore_id?, k=5)`**
- `websearch_to_tsquery('italian', query)`: the model can use `or`, quoted phrases and `-exclude`. The docstring
  teaches it to use `or` between synonyms (by default words are ANDed).
- Matching on a `tsvector` column of `documenti`: title with weight A, content with weight B (generated, GIN index).
  The level is the **document**, not the chunk: there is no need to align with the vectors (in A the channels are
  separate), and full-text search does not depend on the embedding pipeline, which the no-vectors variant does not
  need.
- Returns `totale` (number of matching documents) and the first `k` (max 8) ordered by `ts_rank_cd`, each with
  `doc_id`, `titolo`, `tipo`, `data` and 1–2 highlighted snippets (`ts_headline`).
- **Relevant = contains the terms**: no threshold.
- Zero results → explicit note: try synonyms or remove filters before concluding that it is not documented.
- A query with no useful terms after parsing (stopwords only) → `ModelRetry` with a clear message.
- The returned `doc_id`s go into `seen_ids` (as semantic search does today), not among the opened documents.

**`cerca_semantica`**: today's `cerca_documenti`, with the new name and a docstring that clarifies its role
(concepts and paraphrases, not names or codes). In addition, for credibility with filters at scale, enable pgvector's
iterative HNSW scan (`hnsw.iterative_scan`) if the installed version supports it (≥ 0.8).

### Documents reachable only through tools (my call)

`documenti` is excluded from the relations `query_sql` can query and from the DDL in the prompt, as `documenti_chunks`
already is. Reasons: every access to documents goes through a tracked tool shown in the UI; at scale,
`SELECT contenuto ...` would flood the context; and no "backup" lexical channel through `ILIKE` skews the ablation.

### Configuration and ablation

- New variable `RICERCA_SEMANTICA` (on by default). When off, `cerca_semantica` is not registered among the tools.
- `open_session` accepts the corresponding parameter, so API, CLI and eval use the same path.
- The **system prompt does not name the document search tools**: the specific guidance lives in the docstrings. The
  prompt keeps a tool-independent principle, for example: "before declaring a cause undocumented, search with several
  phrasings and synonyms and use the period and counterparty filters". Principle 3, which today mentions
  `cerca_documenti`, must be reworded.

### API, events, UI

- `events.py`: translation of the new tools' results into `tool_result` (IDs and counts, never the text). A `totale`
  field in `ToolResult` is needed for `elenca_documenti` and `cerca_testo`.
- Frontend (`Passi.tsx`): title, icon, summary and arguments for the three search tools. Example summaries:
  "12 documenti (pagina 1 di 1)", "3 documenti con corrispondenza su 3", "Nessuna corrispondenza".
- **History**: investigations already saved contain `cerca_documenti` events; the UI keeps showing them (legacy
  label). The same applies to the eval's `TABELLE_PER_TOOL` map.

### Data and migration

- Generated column and GIN index in `schema.sql`.
- An already initialised database needs a way to apply them without `--reset` (which also deletes the embeddings),
  in the style of `--comments-only`; alternatively, document `--reset` + reindexing (cheap: 62 documents). Left to
  the implementer.

### Eval

- A new harness option to switch semantic search off; the value ends up in the reports' `meta`.
- `TABELLE_PER_TOOL`: `elenca_documenti` and `cerca_testo` → `documenti`; `cerca_semantica` → `documenti`,
  `documenti_chunks`; legacy key `cerca_documenti` kept.
- A comparison script over the JSON **public reports**: groups by (model, semantic search) and reports, per question
  and in total, the number of `ok` outcomes, the average requests and the average duration.

### Experiment protocol (set before running it)

> Update 2026-10-19: the experiment runs with the harness described in
> `2026-10-19-harness-esperimenti-design.md` (resume, paired exclusions, validity thresholds). The 10-point Task
> Success Rate criterion stays; the model will be the one chosen as final.

- Two variants: **full A** (with `cerca_semantica`) and **A without semantic search**. Same model, same prompt, same
  version of the code.
- Model: `google:gemini-3.5-flash-lite` for all runs (larger models only for isolated trials, outside the
  experiment).
- LLM judge on (`--judge`), with the same flash-lite model: with the judge, `ok` also requires a verdict other than
  `errata`.
- 5 full harness runs per variant.
- Criterion: **the vectors stay only if the full variant gets at least 10 percentage points more `ok` outcomes**
  over the total of 60 runs (12 questions × 5). Otherwise the simpler variant wins and semantic search is removed
  (tool, index, indexer) in a later change.
- No changes to the prompt, docstrings or limits between runs or afterwards, depending on the results.
- Limits unchanged: 25 requests per question, 300 s timeout per question. *(my call)*
- `errore` outcomes *(my call)*: `UsageLimitExceeded` counts as not `ok` (it is a failure of the search strategy, not
  of the infrastructure). Provider errors (HTTP 429/5xx) and timeouts are rerun once; if they fail again they count as
  not `ok` and are reported separately by the comparison script.
- Running the experiment is part of the work (last phase), as is updating the README with the results. If a bug that
  affects the agent's behaviour shows up during the experiment, it is fixed and **all** runs of both variants are
  repeated. *(my call)*
- Stated limit: 12 questions and 62 documents measure quality, not behaviour at scale. Scale is argued through the
  design (indexes, pagination, limits).

### Tests

- Unit: event translation for the new tools; conditional registration of `cerca_semantica`; the prompt does not name
  the document search tools.
- Integration (DB): Italian stemming (an inflected form finds the base), filters, `totale`, the note on empty
  results, retry on an empty query; `elenca_documenti` with pagination and no effect on `seen_ids`; `documenti` not
  queryable from `query_sql`.

### Documentation

README: architecture, list of tools, "Design choices" (why A and not the hybrid), updated "When the evidence is
missing" section; the experiment's results when available.

## Alternatives considered

- **Hybrid search in a single tool (RRF)**: sturdier with small models and a cleaner ablation, but it builds the
  strategy into the tool (against the "the agent decides" thesis) and needs a composite relevance rule. It would be
  the choice with a fixed small model.
- **Metadata only + index in the prompt**: does not cover documents without a counterparty (14 out of 62) and does
  not scale.
- **Improved vectors (re-ranker, per-type thresholds)**: does not make a negative result verifiable.

## Left to the implementer

Ranking normalisation (`ts_rank_cd`), `ts_headline` options, UI icons and texts, migration mechanism, shape of the
comparison script, test details.
