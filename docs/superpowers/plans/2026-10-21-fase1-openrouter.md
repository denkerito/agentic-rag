# Phase 1 — Move to OpenRouter: implementation plan

> **For the implementer:** superpowers:executing-plans (recommended, in this session) or superpowers:subagent-driven-development, one task at a time. The steps use checkboxes.

**Goal:** agent and judge run on Claude through OpenRouter. The harness records the actual cost, does not close runs without the judge's verdict, and stops on credit or key errors.

**Architecture:** `build_model` recognises the `openrouter:` prefix and builds an `OpenRouterModel`, always wrapped in `ModelloGestito` as today. The model has an OpenAI client with no retries of its own, cache and a pinned provider. The harness reads cost and cache tokens from the captured responses. Two new outcomes protect the experiment:
- the `errore_giudice` state, which leaves the combination open;
- the `ErroreFatale` exception, which stops the run.

**Stack:** Python 3.13, pydantic-ai-slim ≥ 2.59 (extras `google`, `openrouter`), pytest, ruff.

**Spec:** `docs/superpowers/specs/2026-10-21-percorso-valutazione-openrouter-design.md`, Phase 1.

## Context

The final model will be Claude Haiku 5.5, with Sonnet 5.5 as judge, both through OpenRouter. Today the code talks only to Gemini. Reading the harness revealed three gaps that would make a paid experiment unreliable:
1. **Cost:** there is no way to see how much a run costs (`PREZZI` is empty).
2. **Judge:** if it fails, the run stays "completata" without a verdict and the Task Success Rate ignores the judge.
3. **Credit or key:** a 401/402/403 closes the combination as `fallita_agente`. With credit running out halfway, the rest of the experiment would become a series of fake failures.

In addition, with the OpenAI-compatible client network errors arrive as `ModelAPIError`, which `ModelloGestito` does not retry. No paid call is made in this phase: the first one is the short trial of phase 2.

## Global constraints

- **Models:** agent `openrouter:anthropic/claude-haiku-5.5`, judge `openrouter:anthropic/claude-sonnet-5.5`. `google:` support stays.
- **Pinned OpenRouter provider:** `{"order": ["anthropic"], "allow_fallbacks": False}`.
- **Effort:** agent at the model's default (no setting), judge `medium`. `max_tokens` = 16,000 for both.
- **Cache:** instructions, tool definitions and last message (TTL 5 min).
- **Retries:** only in `ModelloGestito`; the OpenAI client has `max_retries=0`.
- **Embeddings:** unchanged (Gemini, `GOOGLE_API_KEY`).
- **Fatal errors:** HTTP 401, 402, 403.
- **Manifest:** provider, effort, cache and `max_tokens` are constants in `src/`, not environment variables. The `src/` hash in the manifest covers them, so item 7 of the spec needs no code.
- **Ground truth:** no file in `eval/ground_truth/` is opened; tests use synthetic ground truths, as today.
- **Git:** branch `feat/openrouter-fase1`, one commit per task, messages in the `tipo(area): …` style, in Italian (the project's convention at the time).

## Review Focus

1. **Credit exhausted halfway through the experiment (402):** the experiment stops, the current combination stays open and resuming reruns it without duplicates (test in Task 6).
2. **A judge that always fails** (for example a 400 for an unsupported parameter): no combination closes without a verdict, and the summary declares the experiment invalid instead of inflating the Task Success Rate (Task 7).
3. **Rows from experiments saved before these fields** (Gemini): the summary does not break and shows n/a (Task 8).
4. **OpenAI client disconnecting mid-request:** retried by the wrapper, it does not count as a failure (Task 5).
5. **`OPENROUTER_API_KEY` missing:** a clear message before starting, not dozens of runs in error (Task 2 and Task 4).

---

### Task 1: branch, documents and pydantic-ai upgrade

**Files:** `pyproject.toml`; possible adjustments in `tests/test_agent_unit.py`.

- [ ] `git switch -c feat/openrouter-fase1`. Copy this plan to `docs/superpowers/plans/2026-10-21-fase1-openrouter.md`. Commit the spec and the plan: `docs: percorso di valutazione con OpenRouter e piano della fase 1`.
- [ ] In `pyproject.toml`, `"pydantic-ai-slim[google]"` becomes `"pydantic-ai-slim[google,openrouter]>=2.59"`. Then `.venv/Scripts/python.exe -m pip install -e ".[dev]"`. Expected: `import openai` works.
- [ ] `.venv/Scripts/python.exe -m pytest` and `-m integration` with the DB running. Expected: 178 + 75 green. If `test_client_gemini_non_ritenta_da_solo` breaks because private attributes changed, adapt the inspection path while keeping the assertion: the Gemini client has no `retry_options`.
- [ ] Commit: `build: pydantic-ai 2.59 con supporto OpenRouter`.

### Task 2: OpenRouter in `build_model`

**Files:** `src/agentic_rag/config.py`, `src/agentic_rag/agent/config.py`, `src/agentic_rag/agent/model.py`, `.env.example`, `tests/test_agent_unit.py`.

**Produces:**
- `config.OPENROUTER_API_KEY: str` (env `OPENROUTER_API_KEY`, default `""`).
- In `agent_config`:
  - `AGENT_MODEL` default = `"openrouter:anthropic/claude-haiku-5.5"`;
  - `JUDGE_MODEL: str` = env `JUDGE_MODEL`, default `"openrouter:anthropic/claude-sonnet-5.5"`;
  - `OPENROUTER_PROVIDER = {"order": ["anthropic"], "allow_fallbacks": False}`;
  - `EFFORT: dict[str, str | None] = {"agente": None, "giudice": "medium"}`;
  - `MAX_TOKENS_RISPOSTA = 16_000`.
- In `model`:
  - `OPENROUTER_PREFIX = "openrouter:"`;
  - `impostazioni_openrouter(ruolo: str) -> OpenRouterModelSettings`;
  - `build_model(name, ruolo)` with the same signature.

- [ ] **Failing tests** in `tests/test_agent_unit.py`:
  - `test_impostazioni_openrouter`, on the `"agente"` role:
    - the three keys `openrouter_cache_instructions`, `openrouter_cache_tool_definitions` and `openrouter_cache_messages` are true;
    - `openrouter_provider == {"order": ["anthropic"], "allow_fallbacks": False}`;
    - `openrouter_usage == {"include": True}`;
    - `max_tokens == 16_000`;
    - `"openrouter_reasoning" not in` the settings.
  - Still in `test_impostazioni_openrouter`, on the `"giudice"` role: `["openrouter_reasoning"] == {"effort": "medium"}`.
  - `test_client_openrouter_non_ritenta_da_solo`, with `monkeypatch` on `app_config.OPENROUTER_API_KEY = "chiave-finta"`:
    - `build_model("openrouter:anthropic/claude-haiku-5.5")` is a `ModelloGestito` wrapping an `OpenRouterModel`;
    - `model_name == "anthropic/claude-haiku-5.5"`;
    - the model's OpenAI client has `max_retries == 0`.
  - `test_openrouter_senza_chiave`: with an empty key, `pytest.raises(SystemExit, match="OPENROUTER_API_KEY")`.
- [ ] Run: `pytest tests/test_agent_unit.py -k openrouter`. Expected: FAIL (missing import).
- [ ] **Implementation in `build_model`:**
  - the `openrouter:` branch builds `AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=…, max_retries=0)` and passes it to `OpenRouterProvider(openai_client=…)`;
  - then creates `OpenRouterModel(name without the prefix, provider=…, settings=impostazioni_openrouter(ruolo))`;
  - without a key it raises `SystemExit("OPENROUTER_API_KEY non impostata (vedi .env.example)")`. It is the same pattern as `open_session` for `DATABASE_URL_AGENT`, which `esegui_domanda` already turns into a configuration error.
- [ ] Update `.env.example`: `OPENROUTER_API_KEY=`, the new `AGENT_MODEL` and `JUDGE_MODEL` defaults commented out, and a note that `GOOGLE_API_KEY` is used for the embeddings.
- [ ] Run: `pytest tests/test_agent_unit.py`. Expected: PASS.
- [ ] Commit: `feat(agent): modelli OpenRouter con cache e provider fissato, tentativi nel wrapper`.

### Task 3: judge on Sonnet

**Files:** `src/agentic_rag/eval/giudice.py`, `src/agentic_rag/eval/esperimento.py` (`cmd_esegui`, `--judge-model` help), `src/agentic_rag/eval/__main__.py` (help and `meta["giudice"]`), new `tests/test_eval_giudice.py`.

**Uses:** `agent_config.JUDGE_MODEL` (Task 2).

- [ ] **Failing test:** `test_il_giudice_usa_judge_model_senza_temperatura`.
  - `monkeypatch` on `giudice.build_model` with a function that records `(name, ruolo)` and returns a `FunctionModel`.
  - The `FunctionModel` saves `info.model_settings` and answers with the output call `{"verdetto": "corretta", "motivazione": "m"}`.
  - Assert: `name == agent_config.JUDGE_MODEL`, `ruolo == "giudice"`, `(model_settings or {}).get("temperature") is None`.
- [ ] Run. Expected: FAIL.
- [ ] **Implementation:**
  - `giudica` uses `build_model(model or agent_config.JUDGE_MODEL, ruolo="giudice")` and drops `model_settings=ModelSettings(temperature=0)`;
  - both CLIs use `args.judge_model or agent_config.JUDGE_MODEL` when `--judge` is on;
  - the help texts state the new default.
- [ ] Run `pytest`. Expected: PASS. Commit: `feat(eval): giudice su JUDGE_MODEL, senza temperatura`.

### Task 4: environment check per provider

**Files:** `src/agentic_rag/eval/ambiente.py`, calls in `esperimento.py` and `__main__.py`, `tests/test_eval_ambiente.py`.

**Produces:** `controlla_ambiente(modelli: Sequence[str] = (), db_url: str | None = None, google_key: str | None = None, openrouter_key: str | None = None) -> list[str]`. The `api_key` parameter becomes `google_key`.

- [ ] **Failing test:** `test_chiave_openrouter_richiesta_solo_se_serve`.
  - With `["openrouter:anthropic/claude-haiku-5.5"]`, `db_url=""`, `google_key="k"` and `openrouter_key=""`, one problem contains `OPENROUTER_API_KEY`.
  - With `["google:m"]`, no problem contains `OPENROUTER_API_KEY`.
  - The two existing tests are updated to `google_key=`.
- [ ] **Implementation:**
  - `GOOGLE_API_KEY` is always required, with the message "…(serve agli embedding della ricerca semantica)";
  - `OPENROUTER_API_KEY` is required if a model starts with `openrouter:`;
  - `cmd_esegui` passes the variants' models plus the judge;
  - the battery CLI passes `args.model or AGENT_MODEL` plus the judge if `--judge`.
- [ ] Run `pytest`. Expected: PASS. Commit: `feat(eval): il controllo dell'ambiente verifica la chiave del provider usato`.

### Task 5: retrying the OpenAI client's transport errors

**Files:** `src/agentic_rag/agent/tentativi.py` (`da_ritentare` and the `ERRORI_RETE` comment), `tests/test_agent_tentativi.py`.

- [ ] **Failing test:** in `test_da_ritentare` add:
  - `assert da_ritentare(ModelAPIError("openrouter:m", "Connection error."))`;
  - `assert not da_ritentare(ModelHTTPError(status_code=402, model_name="m"))`.
- [ ] **Implementation:** in `da_ritentare`, after the `ModelHTTPError` branch (a subclass, which must be checked first), `isinstance(e, ModelAPIError)` returns `True`. These are the connection errors and the bodies without a completion that pydantic-ai reports as transient.
- [ ] Run `pytest tests/test_agent_tentativi.py`. Expected: PASS. Commit: `fix(agent): ModelloGestito ritenta gli errori di trasporto del client OpenAI`.

### Task 6: fatal errors stop the run

**Files:** `src/agentic_rag/eval/runner.py`, `esperimento.py` (`cmd_esegui`), `__main__.py`, `tests/test_eval_unit_runner.py`, `tests/test_eval_esperimento.py`, `tests/test_eval_integration.py`.

**Produces** in `runner.py`:
- `CODICI_FATALI = (401, 402, 403)`;
- `class ErroreFatale(Exception)`, with message `nome_errore(e)`, for example `"ModelHTTPError 402"`;
- `errore_fatale(e: BaseException) -> bool`, true for a `ModelHTTPError` with a code in `CODICI_FATALI`.

- [ ] **Failing tests:**
  - **Unit:**
    - `errore_fatale` is true for `ModelHTTPError` 401, 402 and 403, false for 400, 429 and 503;
    - `errore_di_infrastruttura(ModelHTTPError(402, …))` stays false.
  - **Unit, experiment:**
    - a fake executor raises `ErroreFatale` on the second combination: `pytest.raises(ErroreFatale)` around `esegui_esperimento`, and the JSONL has exactly 1 line;
    - resuming with an executor that always answers ok closes all combinations, without duplicates, and the second combination has `tentativo == 1`.
  - **Integration:**
    - a `FunctionModel` that raises `ModelHTTPError(402, "m")` makes `esegui_domanda` raise `ErroreFatale` (`build_model` replaced as in the other tests);
    - the same with the judge (`giudice.build_model` replaced) answering 402.
- [ ] **Implementation:**
  - in `esegui_domanda`, in the run's `except` and in the judge loop: `if errore_fatale(e): raise ErroreFatale(nome_errore(e)) from e`. The connection is closed anyway in the `finally`.
  - `cmd_esegui` catches `ErroreFatale` and prints: "Fermato per {e}: credito esaurito o chiave non valida. Le esecuzioni concluse sono salvate: ricarica o correggi la chiave e rilancia `esegui --etichetta X`." Then it exits without a summary.
  - The battery CLI treats it like a `KeyboardInterrupt` (`interrotta=True` plus a message).
- [ ] Run `pytest` and `pytest -m integration`. Expected: PASS. Commit: `fix(eval): credito esaurito o chiave non valida fermano l'esperimento`.

### Task 7: a judge without a verdict leaves the combination open

**Files:** `runner.py` (`Stato`, `esegui_domanda`), `riepilogo.py` (`riepiloga`, `markdown`), runner, experiment, summary and integration tests.

**Produces:** `Stato` includes `"errore_giudice"`, which is not in `STATI_CHIUSI`. The summary adds the field `"errori_giudice": int` for each variant.

- [ ] **Failing tests:**
  - **Integration:** a `FunctionModel` judge that always fails (raises `ModelHTTPError(400, "m")`) makes `esegui_domanda` return the `"errore_giudice"` state with outcome `"errore"`, keeping answer, tokens and rejections.
  - **Experiment:** an executor that returns `errore_giudice` for a combination twice, then ok, produces the lines (1, errore_giudice), (2, errore_giudice) and (3, completata). It is the same pattern as the infrastructure test.
  - **Summary:** with an `errore_giudice` line the combination is not closed and `riepiloga(...)["varianti"]["con"]["errori_giudice"] == 1`. If all runs of a variant are in `errore_giudice`, `valido` is false.
- [ ] **Implementation:**
  - in `esegui_domanda`, if the judge is on, the question has a `risposta_attesa` and after `TENTATIVI_GIUDICE` there is no verdict, it returns the `errore_giudice` state with all the run's data;
  - the experiment does not change: states that are not closed stay open and are retried;
  - the battery CLI does not rerun and shows `errore_giudice` as today;
  - the "Esecuzioni" line of the Markdown reports the count.
- [ ] Run `pytest` and `pytest -m integration`. Expected: PASS. Commit: `fix(eval): un'esecuzione senza verdetto del giudice resta da rifare`.

### Task 8: actual cost and cache in the summary

**Files:** `runner.py`, `metriche.py` (`_base`), `riepilogo.py` (remove `PREZZI`; `efficienza`, `riepiloga`, `markdown`), runner, summary and integration tests.

**Produces:**
- `costo_risposte(messaggi: Sequence[ModelMessage]) -> float | None`: sum of `provider_details["cost"]` over the `ModelResponse`s; `None` if no response has a cost, as happens with Gemini or fake models.
- New `RisultatoDomanda` fields: `costo_usd: float | None = None`, `costo_giudice_usd: float | None = None`, `token_cache_lettura: int = 0`, `token_cache_scrittura: int = 0`.
- `efficienza(righe)`: the `modello` parameter goes away. It computes:
  - `costo_medio_usd` and `costo_giudice_medio_usd`: mean over the rows with a cost, `None` if none has one;
  - `quota_input_da_cache`: Σ `token_cache_lettura` / Σ `token_input`, `None` if the input is 0.
- `riepiloga`: per variant and in total, `costo_totale_usd` over **all** rows, including failed attempts and infrastructure errors, because those are paid for too.

- [ ] **Failing tests:**
  - **Unit:** `costo_risposte` with two `ModelResponse`s (cost 0.001 and 0.002) and a `ModelRequest` gives `pytest.approx(0.003)`; without costs it gives `None`.
  - **Summary:**
    - the total also includes an `errore_infrastruttura` row with a cost;
    - rows without the new fields give cost `None` and no exception;
    - 500 tokens read from the cache out of 1000 of input give a share of 0.5;
    - the existing calls to `efficienza(righe, None)` are updated.
  - **Integration:** a `FunctionModel` that returns `ModelResponse(..., provider_details={"cost": 0.001})` produces a public row with `costo_usd == approx(0.001 × number of responses)`.
- [ ] **Implementation:**
  - in `esegui_domanda` (successful and failed) the cost comes from `costo_risposte(messaggi)` and the cache tokens from `usage.cache_read_tokens` and `usage.cache_write_tokens`;
  - each judge attempt runs inside its own `capture_run_messages()` and its cost is added up;
  - `_base` adds the four fields to the row;
  - old rows are read with `r.get(...)`;
  - the Markdown adds at the top the line "costo: X $ (agente A $, giudice G $) su N esecuzioni", or "n/d".
- [ ] Run `pytest` and `pytest -m integration`. Expected: PASS. Commit: `feat(eval): costo reale da OpenRouter e quota di input da cache nel riepilogo`.

### Task 9: documentation and final check

**Files:** `README.md`.
- Architecture: "LLM (Gemini)" becomes Claude via OpenRouter.
- Local setup requirements: `OPENROUTER_API_KEY`, plus `GOOGLE_API_KEY` for the embeddings.
- Main variables: `JUDGE_MODEL`.
- Tests and evaluation section: the default judge and the cost line.

- [ ] Update the README.
- [ ] Full check, without paid calls:
  - `.venv/Scripts/python.exe -m pytest`: all green.
  - `.venv/Scripts/python.exe -m pytest -m integration`, with the DB running: all green.
  - `.venv/Scripts/python.exe -m ruff check src tests`: "All checks passed!".
  - `.venv/Scripts/python.exe -m agentic_rag.eval --dry-run`: prints only the structure, as today.
  - with `OPENROUTER_API_KEY` set, `python -c "from agentic_rag.agent.model import build_model; print(build_model(), build_model(ruolo='giudice'))"` builds the models without calling the network.
- [ ] Commit: `docs: README per Claude via OpenRouter`. Branch and PR are to be decided after the review.

## End-to-end verification

In this phase all verification is local and free: unit tests, integration tests on the real DB with fake models, `ruff` and the dry run. The first real call to OpenRouter is the short trial of phase 2, which checks on the real service what is tested here with fakes:
- cache read from the second request;
- cost equal to the one shown by OpenRouter;
- a verdict in every run;
- a clean stop with an invalid key.
