# Path: from the Gemini evaluation to the final experiment with Claude via OpenRouter

Status: draft · 2026-10-21

## Why

We need two results, with a budget of about $10 and without rerunning the experiments several times:
1. **Decision:** keep semantic search or not (criterion already set: at least 10 more points of Task Success Rate).
2. **Benchmark for the CV:** citable metrics, with the project frozen and on a new test set.

The agent moves to **Claude Haiku 5.5** and the judge to **Claude Sonnet 5.5**, both through **OpenRouter**.

## Goals, non-goals, anti-goals

- **Goals:** a single paid experiment, preceded by trials that cost cents; the actual cost of each investigation recorded by the harness; no run passing for an agent failure when the problem is credit or the network.
- **Non-goals:** changing the embeddings (they stay on Gemini, see below); parallelising the experiment; optimising the prompt for Haiku beyond the bare minimum.
- **Anti-goals:** tuning prompts, thresholds or tools by looking at the ground truth (`AGENTS.md`); choosing metrics or criteria after seeing the results; an experiment launched and then invalidated by a harness bug found halfway through.

## Verified facts (2026-10-21)

| | OpenRouter ID | Input | Cache read | Cache write (5 min) | Output (reasoning included) |
|---|---|---|---|---|---|
| Haiku 5.5 (prompt under 100K tokens) | `anthropic/claude-haiku-5.5` | $0.10 / M | $0.01 / M | $0.125 / M | $0.50 / M |
| Sonnet 5.5 | `anthropic/claude-sonnet-5.5` | $2 / M | $0.10 / M | $2.50 / M | $10 / M |

- OpenRouter does not mark up the inference price; it keeps **5.5% on credit purchases**.
- The cache for Anthropic models must be **enabled explicitly** (`cache_control`). pydantic-ai does it with `openrouter_cache_instructions`, `openrouter_cache_tool_definitions` and `openrouter_cache_messages`.
- OpenRouter returns the **actual cost** of each response. pydantic-ai exposes it in `ModelResponse.provider_details["cost"]`.
- Reasoning ("thinking") is billed as output. The `reasoning_details` must be sent back unchanged between one tool call and the next, and pydantic-ai already does this.
- The Anthropic endpoints on OpenRouter do not list `temperature` among the supported parameters. The judge currently sets it to 0 (`eval/giudice.py`).
- With the OpenAI-compatible client, network errors arrive as `ModelAPIError`, which `ModelloGestito` currently **does not retry**: it retries only temporary HTTP codes, Gemini errors and `httpx` errors.
- A **402 (credit exhausted)** or a 401/403 currently closes the combination as `fallita_agente`. If credit ran out halfway through the experiment, all remaining combinations would be counted as agent failures.
- The installed pydantic-ai version is 2.54; the latest is 2.59.

## Choices already made (mine, to confirm while reading)

- **Embeddings stay on Gemini**, moved to `gemini-embedding-2` (key `GOOGLE_API_KEY`): documents reindexed and `SEARCH_MAX_DISTANCE` recalibrated by hand to 0.30 with queries not from the test set (relevant 0.20-0.24, company-related but absent ≥ 0.32, off-topic ≥ 0.43).
- **Provider pinned to Anthropic** on OpenRouter (`order: ["anthropic"]`, `allow_fallbacks: false`). Needed for reproducibility and for cache reads. If Anthropic is down, the errors are infrastructure errors, retried by `ModelloGestito` and by the final pass.
- **Effort:** Haiku at its default (`medium`), Sonnet judge at `medium`. The judge is the most expensive item.
- **Cache on** for instructions, tool definitions and the last message.
- **Retries in the wrapper, not in the client** (`max_retries=0` on the OpenAI client), as already done for Gemini: this keeps the waits measured.

## Open decisions (yours)

1. **One or two experiments.** *Decided on 2026-10-22: B.* The current 12 questions became the development set (see "Review of the development ground truth"), so the final experiment runs only on the new test set.
   - **B (recommended):** a single experiment on the new test set, with both variants. The CV gets the table with both; the product keeps the winner. The winner's number is slightly optimistic because it comes from the same experiment that chose it; the criterion set in advance and showing both variants make up for it.
   - **A:** ablation on the current set, then a benchmark of the winner alone on the new set. It is cleaner and costs about $2-4 more.
2. **Repetitions: 3 or 5.** *Decided on 2026-10-25: 3.* The interval is computed on per-question means, so it depends mostly on the number of questions: two more repetitions reduce the noise only a little and would cost about $3 and 3 hours more, removing the reserve for a rerun. The actual cost is now known: about $0.01 per investigation with the judge (see "Outcome of phase 2"). With 12 questions and one repetition, 5 questions out of 12 changed outcome between the two variants: repetitions are needed.
3. **Size of the new test set.** *Decided on 2026-10-23: 50-60 questions* (in `eval/ground_truth_finale/`, guide in `docs/superpowers/plans/2026-10-23-test-set-finale.md`). Cost is no longer the constraint; the time to write the ground truth is.
   - **25 questions** (about $1.5 with 3 repetitions): enough for the product decision. With 12 questions a single one is worth 8 points, with 25 it is worth 4.
   - **50-60 questions** (about $3): needed if we want to claim that the vectors "are not needed" (see point 5).
4. **Ground truth and git.** *Decided on 2026-10-23:* `eval/ground_truth_finale/` is in `.gitignore` and off-limits to the assistant until the end of the experiment (`AGENTS.md`). The two current files are tracked in git, while the README says the ground truth is outside git. I would keep the new set out (`.gitignore`), at least until the end of the experiment. *Update 2026-11-11:* experiment over, the set is in git (see `AGENTS.md`).
5. **Non-inferiority as a secondary analysis.** *Decided on 2026-10-23: yes*, we report the upper bound of the 95% CI of `con − senza`. The criterion decides on the point estimate (`con − senza ≥ 10`): if it is not met, the correct sentence is "semantic search did not deliver the required improvement", not "it is not needed". Supporting the latter requires the upper bound of the 95% CI of `con − senza` to be below 10 points. With 25 questions the interval will be about ±20 points wide; on the order of 60-100 questions are needed (rough estimate). If we want it, it must be added before seeing the data.
6. **Main metric.** *Decided on 2026-10-23:* Task Success Rate and Answer Accuracy reported **with the same weight**; the decision criterion stays on Task Success Rate (+10 points), set before the data. Initial proposal: Task Success Rate stays, as set on 2026-10-19 (after the fix to how numbers are measured, see below). Answer Accuracy and the share of `errata` answers are reported as secondary. Changing the main metric now would be a choice made after seeing the batteries.

## Phases

### Phase 1 — Move to OpenRouter (code, cost 0)

1. Update pydantic-ai and add OpenRouter support. Add `OPENROUTER_API_KEY` to `config.py`, `.env.example` and `controlla_ambiente`; the Gemini key stays for the embeddings.
2. In `build_model`, the `openrouter:` prefix builds the OpenRouter model with cache, pinned provider and effort. The judge has its own default model (`JUDGE_MODEL`). `temperature=0` is removed from the judge.
3. In `ModelloGestito`, also retry the transient errors of the OpenAI client (`ModelAPIError` without an HTTP code).
4. **Touch-up 1 — actual cost:** each run records the cost returned by OpenRouter (agent and judge separately) and the tokens read from and written to the cache. The summary shows cost per investigation, total cost and the share of input served from the cache. No price table is needed.
5. **Touch-up 2 — judge:** with the judge on, a run without a verdict stays open (it is retried in the final pass) and the summary counts these cases.
6. **Touch-up 3 — fatal errors:** 401, 402 and 403 stop the experiment with a clear message and leave the current combination open. Once credit is topped up, it resumes with just `--etichetta`.
7. Model settings that come from environment variables (provider, effort, cache) go into the manifest, so a resume with different settings is refused.
8. Unit and integration tests with a fake model, `ruff`, README.

**Move on to phase 2 when:** all tests are green and `src/` is committed.

### Phase 2 — Short trial (about $0.10-0.30)

On the current set: 2 questions (one normal and one honest) × 2 variants × 1 repetition, with the judge, interrupted by hand once and resumed. First, for free: launch it with an invalid key and check that it stops without closing combinations.

**Checks on the summary:**
- zero infrastructure errors and no timeouts;
- every run has the judge's verdict;
- cache reads above zero from the second request onwards;
- the recorded cost matches the one OpenRouter shows in the account's activity;
- average cost per investigation and per verdict.

If Haiku misbehaves, for example long loops or answers often rejected by the validator, the prompt is tuned by trying our own questions, not the ground truth ones, and the trial is repeated.

Optional: a development battery on the current set, 12 questions × 1 repetition (about $0.30), to see the behaviour across all modes. It should be read as a functioning signal, not as a list of things to fix question by question.

**Move on to phase 4 when:** all checks pass and the cost per investigation is known.

### Phase 3 — New test set (yours, in parallel with phases 1-2)

- Same schema as the current one, same distribution of modes (normal, honest, unanswerable, regular), 20-30 questions, written without looking at the agent's answers.
- A folder separate from the current one; the harness reads it with `--gt`. `AGENTS.md` must be updated so the access ban also covers the new folder.
- Validation with `python -m agentic_rag.eval --dry-run --gt <folder>`: all expected queries must run. With more than 25 expected numerical values the numbers check does not apply.

### Phase 4 — Freeze

Commit and tag (for example `eval-v1`). From here `src/` does not change until the end of the experiment: the manifest enforces it.

### Phase 5 — Experiment (about $2-5 with 3 repetitions)

```bash
python -m agentic_rag.eval.esperimento esegui --etichetta finale --gt <new-folder> \
    --variante con:semantica=1 --variante senza:semantica=0 --ripetizioni 3 \
    --judge --criterio "task_success_rate:con-senza>=10"
```

Before launching it:
- set a **credit limit on the key** on OpenRouter, for example $8;
- enable **billing on Gemini**: the free embedding quota (1,000 a day) ran out on 2026-10-22, when every integration test run rebuilt the index (about 200 embeddings). Tests now use fake embeddings in a rolled-back transaction and cost about 6 calls, but the experiment's `con` variant uses a few hundred;
- keep the PC awake.

Interruptions are resumed with just the label. At the end, validity (excluded ≤ 10% per variant) and the verdict are checked.

### Phase 6 — Judge validation (yours, about an hour, cost 0)

`etichette --campione 30`, then you fill in the sheet blind, then `kappa`.

### Phase 7 — Results

- **README and CV:** table of the two variants with 95% intervals, the judge's κ, cost per investigation.
- **Product:** `RICERCA_SEMANTICA` is set according to the verdict.
  - *Decided on 2026-11-10:* semantic search is always included, as a product choice: with larger archives and less controlled language it is considered indispensable. In the final experiment it did not give a measurable improvement (+0.7 Task Success Rate points, 95% CI −2.0 to +3.3), and the variant with semantic search is not inferior. The `RICERCA_SEMANTICA` switch has been removed; only the harness turns it off, for the ablation (`--senza-semantica`, `semantica=0` variants).
- The Gemini reports stay as history.

## Outcome of phase 2 (2026-10-22)

Public report data only (`eval/reports/esperimenti/`): no ground truth values.

### Short trial and measured cost

`prova` (2 questions × 2 variants, with the judge): $0.053 in total, no infrastructure errors, every run with a verdict, cache at 84-85% of the input. In the batteries: about **$0.004 per agent investigation and $0.005 per verdict**.

### Development battery as a functioning check

Thresholds set **before** launching it (for the `senza` variant):
- zero infrastructure errors and timeouts, every run with the judge's verdict;
- no invented cause (False Acceptance Rate 0);
- at most 2 `errata` answers out of 12;
- at least 5 `ok` out of 12 (the old Gemini battery, vectors only and without a judge, had scored 5/12).

| | `senza` (`batteria-senza`) | `con` (`batteria-con`) |
|---|---|---|
| Task Success Rate | 3/12 | 4/12 |
| Judge: correct / partial / wrong | 9 / 3 / 0 | 7 / 5 / 0 |
| Invented causes | 0/2 | 0/2 |
| Infrastructure errors, without verdict | 0, 0 | 0, 0 |
| Average requests | 6.6 | 5.7 |

`senza` does not meet the `ok` threshold; the other three are met. Rule set before launching `con`: if `con` also scores at most 4/12, the incompleteness depends on the model or the measurement, not on v2. That is what happened. The `ok` questions of the two variants coincide on just one: 5 questions out of 12 changed outcome, so most of the difference between two single runs is noise.

### Probes on our own questions

Five questions written on the database, on parts of the data without anomalies and therefore far from the test stories, with the reference answer computed in SQL. Two runs each on the `senza` variant.
- **Cited IDs complete in 10 runs out of 10.** Simple questions close in 2-3 requests: few requests do not mean an incomplete answer.
- The "missing" numbers had two causes:
  1. **measurement:** the harness counted only the conclusion and `numeri[].valore`, while the agent often writes the values of the two periods in `numeri[].descrizione` ("April 1,100 → May 450") and the difference in the value;
  2. **view without sources:** `v_margine_mensile` had no `fonti` column, the validator rejects numbers without sources, and the agent moved the revenue, cost and margin totals into `limiti`, where they do not count.
- The IDs missing in the batteries **do not reproduce** on our own questions and remain unexplained. The dataset's documented causes are the test stories, so probes cannot be written on them without overlapping with the ground truth.

### Fixes (found with the probes, not by looking at the ground truth)

- **A, measuring numbers** (`eval/numeri.py`): numbers in `numeri[].descrizione` also count. Those in `limiti` do not: that is where unverified things go, and counting them would reward numbers without sources.
- **B, sources in the margin** (`db/schema_views.sql`): `v_margine_mensile` exposes `fonti`; the views are updated with `init --views-only`.
- **Client closed after every question and every verdict** (`agent/model.py`, `eval/runner.py`, `eval/giudice.py`): OpenRouter's `AsyncOpenAI` was not being closed. With one `asyncio.run` per question, the garbage collector closed it in the next question's loop and the log showed `RuntimeError: Event loop is closed`. No effect on the results, but the tracebacks could have hidden real errors in the experiment log. The first fix closed only the agent's client and its check ran without the judge; `batteria2-*` showed that the judge's one remained. The judge used `run_sync`, which leaves the client tied to an orphaned event loop. Now agent and judge use the same `poi_chiudi`, and the reproduction with the judge on goes from 2 tracebacks to 0.

Rerunning the probes after A and B, all answers are complete. The only exception comes from an error in the reference answer: it gave the taxable amount, while the agent reports the total including VAT. The prompt was not changed.

**Consequences:** today's batteries were measured before A and B and are not comparable with later runs. Before the freeze, the functioning check is rerun on both variants, with the same thresholds.

### Functioning check after A and B (`batteria2-*`)

| | `senza` (`batteria2-senza`) | `con` (`batteria2-con`) |
|---|---|---|
| Task Success Rate | 2/12 | 4/12 |
| Judge: correct / partial / wrong | 10 / 2 / 0 | 8 / 3 / 0 (11 completed) |
| Invented causes | 0/2 | 0/2 |
| Infrastructure errors, without verdict | 0, 0 | 0, 0 (1 agent failure: `UnexpectedModelBehavior`) |

The check is **not passed again**: `senza` scores 2/12 `ok` against the 5 required, while the other thresholds are met. A and B did not change the Task Success Rate on the test questions. Across four batteries, out of 47 completed answers: no `errata`, no invented cause, cited IDs at 70-76% and numbers found at 70-73%.

On the probes the agent is complete, so what is missing is something the ground truth expects. To understand it, the private reports were read: the 12 questions became the **development set** (`AGENTS.md`) and no longer serve to measure.

## Review of the development ground truth (2026-10-22)

Reading of the four batteries' private reports and check of every ID and number against the DB and the CSVs. Of the 10 `ko` in `batteria2-senza`, about two and a half are shortcomings of the agent (Q4, Q9 and half of Q1). The others come from errors or excessive requirements in the ground truth and the harness. The judge never gave `errata`.

### Factual errors fixed

| | Was | Fixed (checked against the data) |
|---|---|---|
| Q6 / ST-03 | Barilli €291,500, 27.51% | €284,000 out of €1,059,400, **26.81%** (the expected query said so too). The judge penalised the right answer |
| Q7 / ST-04 | average travel about €2,100, +210%; invoices `FATT-P-2025-0182`…`0193` | average **€1,850** (every other month), +€4,650, +251%; November invoices `0197`…`0208` (the others are from June-September) |
| Q10 | travel aggregated as the fastest-growing "category" | aligned with the expected query, by account: 64.01 +€2,250 in absolute value, 64.03 +266.7% in percentage, then 61.02 +€1,360. The aggregated reading is still accepted |
| Q3 | average of the other months about €79,000 | €80,268.64 |
| Q12 | `SCD-0015` (it is the ISTAT rent adjustment) | `SCD-0019`, reminder of the Altocumulo notice period (15/08/2026) |
| ST-01 | `SCD-0009` (it is an F24 tax payment) | `SCD-0013`, notice deadline of the Nimbus contract |
| ST-02 | `MOV-000084` (it is a payment received from a customer) | `MOV-000069`, payment of the legal invoice (07/04/2025) |

**Harness bug:** the account codes (`64.01`) in the CSVs were read as numbers, and expected queries comparing them as text returned 0 rows. Q7's query was empty.

### Requirements the question does not make, removed

- **Numbers** (the expected query returned cells that no answer reports):
  - Q1: margin in euros instead of as a percentage;
  - Q2 and Q8: taxable amounts only, without VAT and totals;
  - Q5: only the two Barilli invoices before and after the change, instead of every customer's billing in every month (19 values);
  - Q9: the invoice total, not the sum of the two payments.
- **Tables** that forced a path:
  - Q10 `fatture_righe`: the journal entries are an equivalent source;
  - Q12 `scadenzario`: the deadline is in the contract.
- **Q11:** the check for unanswerable questions allows context numbers. An undocumented cause, limitations and a confidence that is not high are still required.

### What stays required, and why

The supporting sources the agent does not look for stay in the ground truth: CTR-001 and DOC-EML-001 in Q1, DOC-PRV-001 in Q3 and Q4, DOC-EML-005 in Q4, DOC-EML-012 in Q9. The agent finds the first document that explains the cause and stops. For the accountant, contract, correspondence and confirmations are extra verifiability, so it is a shortcoming of the agent, not of the ground truth. The review's criterion: the ground truth is fixed where it is wrong or asks for what the question does not ask, never to make the agent pass.

### Guidelines for the new test set

1. The expected query returns **only the numbers the answer must contain**: no side columns (VAT, totals, numeric IDs), and lists only if the question asks for them.
2. Expected tables (`*.csv` in `fonti_attese`) are given only when the path is forced.
3. Every ID and every number in the expected answer is checked against the DB before freezing the set.
4. Expected answer and expected query must say the same thing (same granularity, same definitions).
5. In the queries, codes are compared as text (`categoria = '64.01'`).
6. Validation with `python -m agentic_rag.eval --dry-run --gt <folder>`: all queries `ok` and the expected number of values.

## Preview instead of truncated SQL results (2026-10-22)

`batteria3-senza`, Q9: the only `errata` after the review. The query for invoice pairs returned 873 rows, `query_sql` showed the first 50 with `troncato: true`, and the duplicate pair was on row 841. The agent concluded "no invoice paid twice". A truncated result still looks like a result.

**Rule:** a result is either complete or explicitly a preview.
- **Complete** if the returned JSON fits in `SQL_MAX_CARATTERI = 30,000`. The calibration is based on the agent's 302 SQL queries in the 22/10 batteries: median 1,014 characters, p99 25,643, only 2 above 30,000. The yearly per-account analyses (213 rows) used to be cut at 50 rows and now arrive complete.
- **Preview** above the threshold:
  - `totale_righe` (exact up to 5,000 rows read);
  - 5 sample rows;
  - the profile of every column: distinct and null values; min, max and sum for numbers; date range; values listed if there are at most 10; array lengths;
  - the columns suitable for a `GROUP BY`;
  - a note asking to aggregate or filter before concluding.
- Only the IDs seen, i.e. in the preview and profile, can be cited. A result at the limit costs about 10,000 tokens (about $0.0015 with the cache); a preview costs less than the old 50 rows.

A character budget alone had been discarded: it moves the cut-off point, but a useful row at the bottom stays invisible.

## Proof of absence, principles and confidence (2026-10-23)

Three agent behaviours remained: false "it is not there" answers (Q9), secondary causes and supporting documents not looked for (Q1, Q3, Q4, Q5), and "high" confidence on unanswerable questions (Q11).

**Rules introduced**, the same for `con` and `senza`:
- **Query IDs and proof of absence.** Every `query_sql` has an ID (`Q1`, `Q2`…). A statement "it does not exist / did not happen in the data" is declared in `assenze`, together with the query that proves it. The validator accepts the absence only if the query exists and its result was complete (not a preview) and either empty or with only zero counts; otherwise it triggers the `assenza_non_provata` rejection. A list of candidates does not prove an absence.
- **Principle 3 (two channels):** an absence in the data is checked both in the data and in the documents.
- **Principle 4 (supporting documents):** the explanation must be looked for for every item that explains the change, not only the main one, together with the related documents (contract, formal correspondence, confirmations). The prompt still does not name the search tools.
- **Confidence:** high = verified with the sources; medium = partially verified; low = insufficient data or an unanswerable question.
- **UI:** verified absences appear with a reference to the query, and every SQL step shows its ID.

**Stated limit:** the validator checks completeness and result, not the query's criteria. If the agent searches with the wrong criteria and finds zero rows, the absence passes the check. That case is covered by the confirmation in the documents and by the query being visible to the accountant.

### Verification

- **Replay of Q9** (conversation with the 873-row preview, `senza`, 3 times): duplicate found 3 times out of 3 (previously 2 out of 3). In every replay the validator rejects a first unproven absence, and the agent fixes it.
- **Battery on the development set, 2 repetitions per variant:**

| | `senza` b3 → b4 | `con` b3 → b4 |
|---|---|---|
| Task Success Rate | 6/12 → **16/24 (67%)** | 6/12 → **16/24 (67%)** |
| `errata` answers | 1 → **0** | 0 → **0** |
| Invented causes | 0 → 0 | 0 → 0 |
| Cited IDs / numbers found | 77% / 78% → 89% / 90% | 84% / 95% → 92% / 98% |
| Investigations failed by the agent | 0 → 1 | 0 → 1 |
| Agent cost per investigation | $0.0039 → $0.0055 | $0.0040 → $0.0064 |

- **Improved:**
  - Q9: duplicate found 4 times out of 4, no `errata`;
  - Q11: `ok` 4 times out of 4, low confidence;
  - Q1 `con`: the secondary Nimbus cause is attributed and documented, judge `corretta` (previously `parziale`);
  - Q5: CTR-008 cited.
- **Still open:**
  - supporting documents not cited: CTR-001 (Q1), DOC-EML-005 (Q4), DOC-EML-012 (Q9);
  - Q3, first repetition, in both variants: failed after three answers rejected for sources never seen or numbers without sources, a failure already seen in `batteria2-con` and independent of the new validator;
  - about one `assenza_non_provata` rejection every two investigations, all eventually closed.
- **Cost:** +40-60% per investigation (more searches and more rejections), still low. The final experiment with 25 questions, 2 variants and 3 repetitions would cost about $1.8 with the judge.

**Stop rule:** from here on the agent is no longer tuned on the development set. The remaining `ko`s could only be chased by pushing the agent towards documents specific to these 12 questions. The number that matters will come from the new test set.

## Launch of the final experiment (2026-10-25)

Written before launching `finale` and before seeing any result from the new test set.

- **Command:** `esegui --etichetta finale --gt eval/ground_truth_finale --variante senza:semantica=0 --variante con:semantica=1 --ripetizioni 3 --judge --criterio "task_success_rate:con-senza>=10"`. Code frozen at tag `eval-v1`.
- **Variant order:** `senza` first. The summary uses the first variant as the reference for the paired comparisons, so the table comes out as `con − senza`, in the same direction as the criterion. The criterion does not change.
- **Reading**, on the same paired differences:
  - criterion on the point estimate: `con − senza ≥ 10` Task Success Rate points;
  - non-inferiority: upper bound of the 95% CI of `con − senza` below 10 points;
  - Answer Accuracy reported alongside, with the same weight and the same reading.
- **Validity:** excluded ≤ 10% per variant and imbalance between the variants ≤ 5 points (`riepilogo.validita`).
- **Accepted risk:** a 4xx error from the Gemini embeddings (invalid key, no billing) does not stop the experiment. It ends up as `fallita_agente` with a `ClientError` error in the `con` variant. We chose not to change `src/` before the freeze. It is covered by:
  - a smoke test on the frozen code (development set, 2 questions × 2 variants);
  - a stop rule.
- **Stop rules** (the run is interrupted with Ctrl-C and a decision is made before resuming):
  - a `ClientError` or `APIError` in `con`;
  - infrastructure errors above 5% of a variant's runs;
  - cumulative cost above $6.

## Outcome of the final experiment (2026-10-26)

`finale`: 50 questions × 2 variants × 3 repetitions = 300 runs, all closed. None excluded, 0 infrastructure errors, every run with the judge's verdict. Cost $2.90 ($0.0048 per investigation plus $0.005 per verdict).

| | `senza` | `con` | `con − senza` (95% CI) |
|---|---|---|---|
| Task Success Rate | 93.3% | 94.0% | +0.7 [−2.0, +3.3] |
| Answer Accuracy | 92.3% | 93.3% | +1.0 [−4.0, +6.0] |
| pass^3 | 88% | 90% | |
| Invented causes | 0/29 | 0/29 | |

- **Criterion** (`con − senza ≥ 10` Task Success Rate points): **not met**.
- **Non-inferiority:** shown. The upper bound of the CI is +3.3, below 10 points.
- **Product:** semantic search stays, as a product choice (see phase 7).
- **Judge:** a sample of 30 answers labelled blind. κ −0.05 both on 3 classes and binary, agreement 87%: under the rule set in advance (κ ≥ 0.6), the judge is **not validated**.

## Analysis after the final experiment (2026-11-11)

Done after lifting the ban, on the private reports and on the set. Nothing was fixed: the set no longer serves to measure, and changing metrics or agent now would alter the experiment's numbers after the fact.

- **False Abstention Rate at 65%: it is an artefact of the metric.** The metric treats as "documented cause expected" every normal question that has a document among its expected sources. The 76 abstentions out of 117 fall on 15 questions, almost all without a cause to explain:
  - simple retrievals (#4, #12, #46, #47);
  - contracts (#19-#22, #24);
  - checks whose answer is "no" (#3, #18, #37, #43, #44).

  There, "undocumented cause" is not an error, and 75 of those 76 runs are `ok`. On the questions that really ask for a cause (#2, #6) the agent abstains 1 time out of 12. *Future work:* apply the metric only to questions with a cause to explain (for example from the `tipo` field).
- **The 5 failed runs** are all `UnexpectedModelBehavior`, i.e. answers rejected by the validator until the retries ran out. The rejections are for sources never seen, numbers without sources and unproven absences.
  - #37 (a check whose answer is "no", on personnel costs): 3 runs out of 6 failed, in both variants.
  - #48 and #50 (unanswerable): 1 run each.

  The validator does its job: the agent cannot back with sources an answer it does not find in the data.
- **The 4 disagreements between human and judge.** On review, the error was in the human labels. In 3 cases the judge is stricter: it gives "parziale" where the human had given "corretta", for a contradictory number (#48), a contradicted premise (#34) and relevant documents left out (#50). In the fourth (#45) it is more lenient. So the judge does not inflate the results, and the Task Success Rate (which fails only `errata` answers) is not affected. The review happened with the verdicts known, so the official κ stays −0.05.

## Budget

| Item | Estimate |
|---|---|
| Phases 1, 3, 4, 6 | $0 |
| Phase 2 (plus the optional battery) | $0.10-0.60 |
| Phase 5, 25 questions × 2 variants × 3 repetitions (150 investigations, about 1 cent each plus 1-2 cents per verdict) | $2-5 |
| Reserve for a rerun | $2-5 |
| **Credits to buy** | **$10 (plus the 5.5% fee)** |

The estimates are uncertain by about a factor of 2, mostly because of how much reasoning Haiku does. Phase 2 replaces them with measured numbers.

## Risks

- **Haiku following the prompt differently from Gemini:** it shows up in phase 2, and is fixed before the freeze.
- **Harness bug found after the experiment has started:** forces a new label. Phase 2 and the three touch-ups mitigate it.
- **Pinned provider unavailable:** infrastructure errors, retried. If the exclusions exceed 10%, the experiment is declared invalid and the label is rerun.
- **Statistical power:** even with 25 questions the verdict is a signal. It must be presented with the interval, as the summary already does.
