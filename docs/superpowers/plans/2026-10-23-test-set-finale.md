# Guide: from the new test set to the final results

Full path decided on 2026-10-23. The 12 questions in `eval/ground_truth/` are the development set: we tuned the agent, the validator and the ground truth on them, so they no longer measure anything. The number to cite in the README and in the CV will come **only** from the new test set, written by you and never seen by the assistant.

Legend: **[you]** = you do it · **[Claude]** = you ask Claude in a session · **[together]** = shared decision or check.

---

## Phase 0 · Protection (before creating the folder)

- [ ] **[Claude]** Add the rule to `AGENTS.md`: "The `eval/ground_truth_finale/` folder and the private reports of its experiments are off-limits to the assistant until the end of the final experiment. The assistant knows only their structure; the harness code reads them at runtime without printing their content."
- [ ] **[Claude]** Add `eval/ground_truth_finale/` to `.gitignore` (decision 4 of the spec: the new set stays out of git until the end of the experiment).
- [ ] **[you]** From here on, never paste into the chat questions, expected answers or pieces of the final set's private reports.

## Phase 1 · Three decisions, before writing a single question

They must be taken and written in the spec **before** seeing any result.

| Decision | Options | What it implies |
|---|---|---|
| **Size** | 25 questions · 50-60 questions | 25: enough for the product decision; an interval on the difference between the variants of about ±20 points. 50-60: lets you prove non-inferiority ("the vectors are not needed"); about twice the writing time |
| **Main metric** | Task Success Rate (recommended) · Answer Accuracy alongside | TSR is the criterion set on 19/10; Answer Accuracy and the share of `errata` are reported as secondary anyway |
| **Non-inferiority** | yes · no | Yes: besides the +10-point criterion, the upper bound of the 95% CI of (con − senza) is reported; it is meaningful only with 50+ questions |

- [x] **[you]** Chosen on 2026-10-23:
  - **50-60 questions**;
  - **both metrics reported with the same weight**: the decision criterion stays on Task Success Rate (+10 points, set on 19/10), and Answer Accuracy is presented alongside, not as secondary;
  - **non-inferiority: yes**.
- [ ] **[Claude]** Writes them in the spec, "Open decisions" section, with the date.

## Phase 2 · Writing the test set

### 2.1 Folder and format

Create `eval/ground_truth_finale/` with two files, in the **same format** as the development set:

`domande_test.yaml` (example with made-up values):

```yaml
domande:
  - id: 1
    domanda: "Perché i costi di X sono saliti a maggio?"
    storia_id: "ST-01"            # optional: groups the questions by story
    tipo: "multi-passo"           # the mode is derived from here, see below
    risposta_attesa: >
      Text of the correct answer, with the essential causes and numbers.
    fonti_attese:
      - "DOC-EML-999"             # IDs a complete answer must cite
      - "FATT-P-2025-9999"
      - "fatture.csv"             # table: only if the path is forced
    query_sql: >
      SELECT ...                  # runs on SQLite built from the CSVs in data/csv
```

`storie.yaml` (optional): `storie: [{id: "ST-01", titolo: "..."}]`.

**Mode**, derived from the `tipo` field:
- contains "non rispondibile" → `non_rispondibile`: the agent must say it cannot answer, with a confidence that is not high;
- contains "non documentata" → `onesta`: it must declare the cause undocumented, without inventing it;
- contains "regolare" → `regolare`: no anomaly, the outcome is "it is regular";
- otherwise → `normale`.

### 2.2 Recommended distribution

Similar to the development set, with the "negative" questions added:

| Mode | out of 25 | out of 50 |
|---|---|---|
| normal (documented causes, numbers, comparisons) | 15 | 30 |
| normal with a **correct answer of "no"** (e.g. "are there unpaid invoices?" when there are none), verifiable with a query | 3 | 6 |
| honest (undocumented cause) | 3 | 6 |
| unanswerable | 2 | 4 |
| regular | 2 | 4 |

Vary the types: causes with a single document, causes with several documents, numbers without a cause, accounting checks, deadlines and contracts, comparisons between periods different from those of the development set.

### 2.3 Rules for each question (from the review of the development set)

- [ ] **The expected query returns only the numbers the answer must contain.** No side columns (VAT, totals, numeric IDs, counts nobody asked for). No lists, unless the question asks for them. Above 25 values the numbers check does not apply.
- [ ] **Expected answer and expected query say the same thing:** same granularity, same definitions. Example to avoid: a query per single account and an answer per aggregated category.
- [ ] **Expected sources = the necessary ones.** The document that proves the cause and the decisive invoices or transactions. An answer that cites them all is "complete": do not add side documents unless they are really required.
- [ ] **Tables (`*.csv`) only if the path is forced.** If the answer can be found in two ways, do not name one.
- [ ] **Every ID and every number is checked against the database** before freezing. The development set had 8 factual errors.
- [ ] **In the queries, codes are compared as text** (`categoria = '64.01'`), and the columns are those of the CSVs (`data/csv/*.csv`, with SQLite's `strftime` for dates).
- [ ] **Write the question without looking at the agent's answers** and without trying it on the agent.

### 2.4 Checks before handing over

- [ ] **[you]** `python -m agentic_rag.eval --dry-run --gt eval/ground_truth_finale`: all queries `ok`, a plausible number of expected values, 0 unrecognised sources.
- [ ] **[you]** For each question, open the cited IDs (UI or DB) and reread the expected answer against the data.
- [ ] **[Claude]** **Structural** validation without reading the files: you can ask for a command that prints only counts (modes, number of questions, IDs existing in the DB yes/no). You run the command and show Claude only the counts.

## Phase 3 · Preparing the experiment

- [ ] **[you]** Enable **billing on Gemini** (Google AI Studio → paid plan) and a spending limit.
- [ ] **[you]** On OpenRouter set a **credit limit on the key** (for example $8) and check the balance.
- [ ] **[Claude]** **Freeze:** clean `main`, all tests green, tag `eval-v1`. From here `src/` does not change (the manifest enforces it).
- [ ] **[you]** PC awake and plugged in for the whole run: 1-2 hours with 25 questions, 2-4 hours with 50.

## Phase 4 · Experiment

- [ ] **[you or Claude]** Launch:

```bash
python -m agentic_rag.eval.esperimento esegui --etichetta finale --gt eval/ground_truth_finale --variante con:semantica=1 --variante senza:semantica=0 --ripetizioni 3 --judge --criterio "task_success_rate:con-senza>=10"
```

- If it stops (network, credit, PC), resume with just the label:

```bash
python -m agentic_rag.eval.esperimento esegui --etichetta finale --gt eval/ground_truth_finale
```

- [ ] **[together]** Validity check on the public summary (`eval/reports/esperimenti/finale/riepilogo.md`, which Claude can read): experiment **valid** (excluded ≤ 10% per variant), zero tracebacks, the criterion's verdict.
- Expected cost: about $0.012 per investigation with the judge, i.e. about $1.8 with 25 questions and $3.6 with 50.

## Phase 5 · Judge validation (about an hour)

- [ ] **[you]** `python -m agentic_rag.eval.esperimento etichette --etichetta finale --campione 30` creates a private sheet with 30 answers. Fill it in **blind**: corretta / parziale / errata, without looking at the judge's verdict.
- [ ] **[you]** `python -m agentic_rag.eval.esperimento kappa --etichetta finale` computes Cohen's κ and adds it to the summary.
- Reading: κ ≥ 0.6 means good agreement and a reliable judge; below that, Answer Accuracy must be presented with caution.

## Phase 6 · Results

- [ ] **[Claude]** README: table of the two variants (Task Success Rate, Answer Accuracy, `errata`, invented causes, cost and time per investigation) with 95% intervals, the judge's κ, criterion and verdict.
- [ ] **[together]** The sentence on the result, an honest one:
  - if `con − senza < 10`: "semantic search did not deliver the minimum required improvement (+10 points); difference X [CI]"; with non-inferiority proven: "the variant without vectors is not worse by more than 10 points";
  - if `≥ 10`: "semantic search improves by X points [CI]".
- [ ] **[Claude]** Product: `RICERCA_SEMANTICA` set according to the verdict.
- [ ] **[you]** CV and interview: synthetic dataset (62 documents), development set separate from the final set, criterion set in advance, the judge's κ, cost per investigation. Stated limits: a single dataset, one model (Haiku 5.5), an LLM judge.

---

## Summary of times and costs

| Phase | Who | Time | Cost |
|---|---|---|---|
| 0 Protection | Claude | 10 min | 0 |
| 1 Decisions | you | 15 min | 0 |
| 2 Test set | you | 3-5 h (25) · 6-10 h (50) | 0 |
| 3 Preparation | you + Claude | 30 min | 0 |
| 4 Experiment | machine | 1-4 h | $2-4 |
| 5 Judge | you | 1 h | 0 |
| 6 Results | Claude + you | 1-2 h | 0 |
