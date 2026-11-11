# Vision

> An AI agent that **autonomously investigates** a company's financial data, connecting structured data and documents, to turn them into information an accountant can **verify and use**.

---

## The problem

In an accounting firm, the information about a client company is scattered: invoices, bank transactions, contracts, deadlines, accounting data, correspondence. Answering a question like *"why did the margin fall in August?"* requires:

1. extracting the numbers from several sources;
2. comparing them across periods;
3. identifying the line items responsible;
4. looking for the documents that explain the change;
5. putting it all together into a defensible conclusion.

The work is long, repetitive and hard to automate with traditional tools, because each question needs a different line of analysis.

## The proposal

An agent that carries out **the preliminary analysis** in place of the accountant, and hands it over already verifiable.

```
Accountant ──► question / situation to analyse
                        │
                        ▼
                     AGENT ──► structured data (SQL) + documents (RAG)
                        │
                        ▼
                  multi-step analysis
                        │
                        ▼
Accountant ◄── conclusion + numbers + cited sources
```

It does not replace the accountant. It saves them the gathering and comparing phase, and leaves them the part that needs professional judgement: **checking and deciding**.

### Example

> **Question:** "Why did the margin drop in August?"

The agent does not answer with a guess. It proceeds like this:

1. retrieves August's revenue and costs;
2. compares them with July;
3. finds that costs grew more than revenue;
4. identifies the cost categories responsible;
5. retrieves the related invoices and documents through RAG;
6. looks for an explanation in the documents;
7. returns the answer with its sources.

> **Answer:** "The margin dropped mainly because of the increase in software costs (+34%). I found an increase in the Microsoft subscription from June, supported by invoices X and Y and by contract Z."

## What sets the project apart from a chatbot over documents

| Chatbot / simple RAG | This project |
|---|---|
| Searches for text similar to the question | Plans a line of analysis |
| A single retrieval call | Several steps, each based on the previous result |
| The LLM "calculates" the numbers | Numbers **always** come from SQL queries, never from the model |
| Fluent answer, optional sources | Every statement is linked to a piece of data or a document |
| Always answers | Says "I did not find a cause" when that is the case |

The last point is central: in an accounting context a wrong but convincing answer is worse than no answer.

## Design principles

1. **Verifiability first.** Every conclusion reports numbers and sources (invoice, contract, transaction IDs) that the accountant can open and check.
2. **Numbers are never made up.** Calculations and aggregations go through read-only SQL. The LLM interprets and connects; it does not calculate.
3. **Honesty about uncertainty.** The agent exposes a confidence level and distinguishes what the documents prove from what is a hypothesis.
4. **Reasoning is visible.** The agent's steps (queries run, documents consulted) are shown in the interface: that is how the accountant comes to trust it.
5. **Human in the loop.** The agent prepares, the human checks and decides. No action is taken on the data autonomously.

## MVP scope

### Included

- A fictitious company with 12 months of synthetic data (about 300 transactions, invoices, contracts).
- Structured data: bank transactions, invoices, suppliers, cost categories, deadlines.
- Unstructured documents: contracts and correspondence, indexed for semantic search.
- An agent with tools to query the database, search the documents, compare periods and open a specific document.
- An interface with the question, the reasoning steps in real time, the answer and the sources.
- A small set of test questions with expected answers, to measure whether the agent finds what it should.

### Excluded (on purpose)

- Real client data: for privacy reasons the project uses only synthetic data.
- Integration with accounting software, the Italian e-invoicing exchange system (SdI) or open banking.
- Authentication, multiple companies, multiple users.
- Any writing to the accounting data.
- Proactive mode (automatic anomaly reporting): a possible future evolution, not part of the MVP.

## Synthetic data: the "hidden stories"

The quality of the demo depends on the data. Instead of generating random numbers, we build **stories** for the agent to uncover, for example:

- **Software subscription increase:** a supplier raises its fee from June; the contract allows it, and the invoices confirm it.
- **One-off anomalous cost:** a one-time consultancy explains a cost spike in one month.
- **Revenue drop from one customer:** an important customer cuts its orders; the cause is visible in the correspondence.
- **Case with no explanation:** a change with no documented cause in the data, to check that the agent admits it instead of inventing one.

Each story has an associated question and an expected answer: they are the project's evaluation test.

## Architecture

```
┌────────────┐     ┌──────────────────────────────────────┐
│     UI     │◄───►│                Agent                 │
│  (React)   │     │   loop: plan → use tools → evaluate  │
└────────────┘     └───────┬───────────┬───────────┬──────┘
                           │           │           │
                  query_sql   cerca_documenti   confronta_periodi
                           │           │
                    ┌──────▼───┐  ┌────▼─────────┐
                    │          │  │ Vector store │
                    │ (struct. │  │ (contracts,  │
                    │  data)   │  │ correspond.) │
                    └──────────┘  └──────────────┘
```

### Proposed stack

| Layer | Choice | Reason |
|---|---|---|
| Language | Python | The standard for working with LLMs |
| Agent orchestration | **Pydantic AI** | The line of analysis is decided by the model (a loop with tools); typed, validated output (mandatory sources, confidence, documented cause), dependencies injected into the tools, tests without LLM calls (`TestModel`). If a fixed flow, human-in-the-loop or a proactive mode is needed later, we can move to `pydantic-graph` or reconsider LangGraph |
| LLM | Gemini (free API), default `gemini-3.5-flash-lite`, configurable with `AGENT_MODEL` | Zero cost for the MVP; the free-tier limits must be checked in AI Studio |
| Structured data | PostgreSQL |  |
| Vector store | pgvector |  |
| Backend | FastAPI | Exposes the agent and streams its steps |
| Frontend | React | The fastest option for an interface with streamed steps; the frontend is not the point of the project |
| Observability | Logfire (free tier, native Pydantic AI integration) or structured logs | Makes the reasoning visible, also useful for the portfolio |

### Definition of margin

The margin is **revenue − costs on an accrual basis**, computed from `scritture_contabili` (journal entries) on the Costs/Revenue accounts of the chart of accounts (views `v_economico*`, `v_margine_mensile`). Invoice lines are not enough because salaries, social security contributions and bank fees appear only in the journal entries.

## How success is measured

- **Recall on the hidden stories:** out of N test questions, how often the agent identifies the correct cause.
- **Accuracy of the numbers:** the values cited match those in the database (they always should, by construction).
- **Quality of the sources:** every cited source exists and really supports the statement.
- **Honesty:** on the case with no explanation, the agent says it did not find one.
- **Cost per question:** number of model calls per investigation, to stay within the free limits.

## Roadmap

| Day | Goal |
|---|---|
| 1 | Synthetic data generator with the hidden stories; database schema |
| 2 | XML invoice parsing, document indexing |
| 3 | Agent with tools; the "August margin" case working end to end |
| 4 | Source citation, uncertainty handling, interface with live steps |
| 5 | Evaluation on the test questions, polishing, README, recorded demo |

## Possible evolutions

- **Proactive mode:** the agent analyses the data without a question and reports anomalies (duplicate invoices, transactions without an invoice, deadlines without liquidity).
- **Contract versus reality check:** a systematic comparison between contract clauses and the amounts actually invoiced.
- **Multiple companies** and memory of previous investigations.
- **Integration with a real accounting system** through its exports.
