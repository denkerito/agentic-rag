# Provider retries in the model wrapper: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** the time lost because of the provider (pauses between attempts and the duration of failed attempts on 429/5xx/network) no longer eats into the eval's working time, so an unstable provider no longer produces `fallita_agente` runs.

**Architecture:** the Gemini client stops retrying (`GoogleProvider` without `retry_options`). Retries move into a Pydantic AI `WrapperModel` (`ModelloGestito`), always applied by `build_model` for both the API and the eval. The wrapper sends every attempt through the RPM/TPM limiter and adds to `MisuraAttese` both the duration of the failed attempt and the following pause. The `entro_il_tempo` watchdog already subtracts `misura.secondi`, so it does not change.

**Tech Stack:** Python ≥ 3.13, pydantic-ai 2.54 (`WrapperModel`, `FunctionModel`, `ModelHTTPError`), google-genai 2.28, httpx, pytest.

**Spec:** decisions taken in chat on 2026-10-20 (reported below), to be read together with `docs/superpowers/specs/2026-10-19-harness-esperimenti-design.md`. The "Provider retries" section of that design is updated in Task 4.

### Decisions (from the chat)

1. **Approach A:** retries live in the model wrapper, not in the HTTP client. There is no heuristic reclassification.
2. **Both the pause and the duration of the failed attempt** are excluded from working time.
3. The behaviour applies **to the API too**: there is a single `build_model`.

### My choices (to confirm in review)

- **Cadence:** the same as today, i.e. 5 attempts in total with pauses of 10, 20, 40 and 60 s plus a jitter between 0 and 1 s. The same errors as today are retried: HTTP 429, 500, 502, 503 and 504, plus `httpx.TimeoutException` and `httpx.ConnectError`.
- **Per-attempt timeout:** 120 s (`asyncio.wait_for`), also retriable. Without this limit, a stuck request would reach pydantic-ai's HTTP timeout (600 s) and trigger `TempoScaduto` (300 s) before failing.
- **Streaming:** only opening the stream is retried. An error after the first event propagates as is, otherwise the API's interface would see duplicate events.
- **New `tentativi_provider` field:** holds the number of failed attempts per run. It goes into the experiment rows and into the summary's efficiency, so you can see whether one variant suffered more provider instability. The `attesa_limitatore_media_s` field becomes `attesa_media_s`, because it now also includes the retry pauses.

## Global Constraints

- Names, docstrings, comments and commit messages in Italian, in the style of the neighbouring files.
- Retriable codes: `CODICI_TEMPORANEI = (429, 500, 502, 503, 504)`.
- Cadence: `tentativi=5`, `attesa_iniziale_s=10.0`, `attesa_max_s=60.0`, `jitter_s=1.0`, `timeout_tentativo_s=120.0`.
- Waits are added to `MisuraAttese` in steps of `PASSO_ATTESA_S` (1 s), already defined in `limiti.py`. The watchdog must see them grow during the pause, not only at the end.
- `asyncio.CancelledError` is never retried, because it is how `entro_il_tempo` stops the agent.
- Tests run with `.venv/Scripts/python.exe -m pytest -q` (integration tests are excluded by default). Lint runs with `.venv/Scripts/python.exe -m ruff check src tests`.
- Every commit ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Code and tests **do not read** `eval/ground_truth/` (see AGENTS.md).

## Review Focus

1. **Stream error after the first event:** it is not retried and does not duplicate events. Test `test_stream_errore_dopo_il_primo_evento_non_si_ritenta` (Task 2).
2. **Cancellation during the pause** (the watchdog or the user stops the investigation): the task stops immediately and no further attempt starts. Test `test_cancellazione_durante_la_pausa_si_propaga` (Task 2).
3. **Non-transient errors** (400, 404 non-existent model, `UsageLimitExceeded`, `UnexpectedModelBehavior`): they propagate on the first hit. Tests `test_da_ritentare` (Task 1) and `test_errore_non_temporaneo_non_si_ritenta` (Task 2).
4. **API without an active `misura_attese()`:** the wrapper works and raises no exceptions. Test `test_senza_misura_attiva_funziona` (Task 2).
5. **Experiments saved before this change,** with rows without `tentativi_provider`: `riepilogo` does not fail and counts 0. Test `test_efficienza_righe_senza_tentativi_provider` (Task 4).

---

### Task 1: Retry policy and measured waits

**Files:**
- Create: `src/agentic_rag/agent/tentativi.py`
- Modify: `src/agentic_rag/agent/limiti.py`, which gets `MisuraAttese`, the addition of waits and the new `dormi_misurato`
- Test: `tests/test_agent_tentativi.py` (new), `tests/test_agent_limiti.py`

**Interfaces:**
- Produces in `limiti.py`:
  - `MisuraAttese.tentativi_falliti: int = 0`, a new field next to `secondi`;
  - `def aggiungi_attesa(secondi: float) -> None`: adds to the active measurement, if there is one, otherwise does nothing;
  - `def conta_tentativo_fallito() -> None`;
  - `async def dormi_misurato(secondi: float, dormi: Callable[[float], Awaitable[None]] = asyncio.sleep) -> None`: sleeps in steps of `PASSO_ATTESA_S` and calls `aggiungi_attesa` after each step.
- `Limitatore.attendi` uses `aggiungi_attesa` instead of accessing `_misura` directly.
- Produces in `tentativi.py`:
  - `CODICI_TEMPORANEI: tuple[int, ...]`;
  - `@dataclass(frozen=True) class PoliticaTentativi`, with the fields and defaults listed in the Global Constraints;
  - `POLITICA = PoliticaTentativi()`;
  - `def pausa(politica: PoliticaTentativi, n: int, casuale: Callable[[], float] = random.random) -> float`: the pause after the `n`-th failed attempt (n starts at 1), equal to `min(attesa_iniziale_s * 2**(n-1), attesa_max_s) + jitter_s * casuale()`;
  - `def da_ritentare(e: BaseException) -> bool`.

- [ ] **Step 1: Write the failing tests**

```python
def test_pausa_segue_la_cadenza_di_prima() -> None:
    assert [pausa(POLITICA, n, casuale=lambda: 0.0) for n in range(1, 6)] == [10, 20, 40, 60, 60]
    assert pausa(POLITICA, 1, casuale=lambda: 1.0) == 11

def test_da_ritentare() -> None:
    for codice in (429, 500, 502, 503, 504):
        assert da_ritentare(ModelHTTPError(status_code=codice, model_name="m"))
    assert da_ritentare(genai_errors.APIError(503, {}))
    assert da_ritentare(httpx.ConnectError("giù"))
    assert da_ritentare(httpx.ReadTimeout("lento"))
    assert da_ritentare(TimeoutError())  # timeout del singolo tentativo
    assert not da_ritentare(ModelHTTPError(status_code=400, model_name="m"))
    assert not da_ritentare(ModelHTTPError(status_code=404, model_name="m"))
    assert not da_ritentare(UsageLimitExceeded("limite"))
    assert not da_ritentare(UnexpectedModelBehavior("output non valido"))
    assert not da_ritentare(asyncio.CancelledError())
```

In `tests/test_agent_limiti.py`, reusing the existing `Orologio` class:

```python
def test_dormi_misurato_somma_a_passi() -> None:
    o = Orologio()
    visti: list[float] = []
    async def dormi(s: float) -> None:
        await o.dormi(s)
        visti.append(m.secondi)  # misura vista dal watchdog durante la pausa
    with misura_attese() as m:
        asyncio.run(dormi_misurato(2.5, dormi))
    assert m.secondi == 2.5
    assert visti == [0.0, 1.0, 2.0]  # cresce passo per passo, non tutta alla fine
```

- [ ] **Step 2: Run the tests and check that they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_agent_tentativi.py tests/test_agent_limiti.py -q`
Expected: FAIL with `ModuleNotFoundError: agentic_rag.agent.tentativi` / `ImportError: dormi_misurato`.

- [ ] **Step 3: Implement** the content of the Interfaces block.
  - In `da_ritentare`: a `ModelHTTPError` is retried if `status_code` is in `CODICI_TEMPORANEI`; a `genai_errors.APIError` if `code` is in `CODICI_TEMPORANEI`; `httpx.TimeoutException`, `httpx.ConnectError` and `TimeoutError` are retried too.
  - `CancelledError` is a `BaseException` and must stay excluded.

- [ ] **Step 4: Run the tests and check that they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_agent_tentativi.py tests/test_agent_limiti.py -q`
Expected: PASS (including the 3 limiter tests that were already there).

- [ ] **Step 5: Commit**

```bash
git add src/agentic_rag/agent/tentativi.py src/agentic_rag/agent/limiti.py tests/test_agent_tentativi.py tests/test_agent_limiti.py
git commit -m "feat(agent): politica dei tentativi su 429/5xx e attese misurate a passi"
```

---

### Task 2: `ModelloGestito`, the wrapper with limiter and retries

**Files:**
- Modify: `src/agentic_rag/agent/tentativi.py`, where `ModelloGestito` lands
- Modify: `src/agentic_rag/agent/limiti.py`, from which `ModelloLimitato` is removed (`ModelloGestito` replaces it)
- Test: `tests/test_agent_tentativi.py`

**Interfaces:**
- Consumes: `Limitatore`, `aggiungi_attesa`, `conta_tentativo_fallito`, `dormi_misurato` (Task 1); `PoliticaTentativi`, `pausa`, `da_ritentare` (Task 1).
- Produces: `class ModelloGestito(WrapperModel)` with
  `__init__(self, wrapped: Model | KnownModelName, limitatore: Limitatore | None, politica: PoliticaTentativi = POLITICA, orologio: Callable[[], float] = time.monotonic, dormi: Callable[[float], Awaitable[None]] = asyncio.sleep, casuale: Callable[[], float] = random.random)`.
  It overrides `request` and `request_stream`, with the same signatures as the current `ModelloLimitato`.

Each attempt follows these steps:
1. If there is a limiter, call `await limitatore.attendi()`.
2. Take `inizio = orologio()`.
3. Run the inner request inside `asyncio.wait_for(…, politica.timeout_tentativo_s)`.
4. On an exception for which `da_ritentare` is true, call `aggiungi_attesa(orologio() - inizio)` and `conta_tentativo_fallito()`. If it was the last attempt, re-raise the exception; otherwise call `await dormi_misurato(pausa(politica, n, casuale), dormi)` and try again.
5. On any other exception, re-raise it immediately.
6. If the request succeeds, record the tokens in the limiter as today.

In streaming, the loop wraps only the entry into the inner context manager: with `FunctionModel` and `GoogleModel` the HTTP response or the first event arrive right there. After the `yield` there are no more retries.

- [ ] **Step 1: Write the failing tests**

The tests need:
- a fake `Orologio`, as in `tests/test_agent_limiti.py`;
- a `FunctionModel` built with a function that raises `ModelHTTPError(503)` for the first N attempts and then returns `ModelResponse(parts=[TextPart("ok")])`, advancing the fake clock by 5 s on every failed attempt;
- `casuale=lambda: 0.0`.

```python
def test_503_poi_successo_ritenta_e_misura_tentativo_e_pausa() -> None:
    # 1 tentativo fallito (5 s) + pausa 10 s, poi successo
    with misura_attese() as m:
        risposta = asyncio.run(richiedi(ModelloGestito(fallisce(1), None, orologio=o, dormi=o.dormi, casuale=zero)))
    assert risposta.parts[0].content == "ok"
    assert m.secondi == 15.0 and m.tentativi_falliti == 1 and chiamate == 2

def test_esauriti_i_tentativi_rilancia_l_ultimo_errore() -> None:
    # fallisce sempre: 5 chiamate, pause 10+20+40+60, 5 tentativi da 5 s
    with misura_attese() as m, pytest.raises(ModelHTTPError) as e:
        asyncio.run(richiedi(ModelloGestito(fallisce(99), None, ...)))
    assert e.value.status_code == 503 and chiamate == 5
    assert m.secondi == 130 + 25 and m.tentativi_falliti == 5

def test_errore_non_temporaneo_non_si_ritenta() -> None:  # 400: una chiamata, nessuna attesa
    ...
    assert chiamate == 1 and m.secondi == 0.0

def test_ogni_tentativo_passa_dal_limitatore() -> None:
    # rpm=1: il primo tentativo fallisce a t=0, pausa fino a t=15 (5+10), il secondo attende la
    # finestra fino a t=60 → misura = 5 (tentativo) + 10 (pausa) + 45 (limitatore)
    lim = Limitatore(rpm=1, tpm=None, orologio=o, dormi=o.dormi)
    ...
    assert m.secondi == 60.0 and chiamate == 2

def test_timeout_del_tentativo_ritenta() -> None:
    # politica con timeout_tentativo_s=0.05: il primo tentativo dorme 1 s reale, il secondo risponde
    ...
    assert chiamate == 2 and m.tentativi_falliti == 1

def test_stream_ritenta_l_apertura() -> None:
    # stream_function: 503 prima del primo chunk, poi "ok" → testo "ok", 2 chiamate

def test_stream_errore_dopo_il_primo_evento_non_si_ritenta() -> None:
    # stream_function: emette "a" poi solleva 503 → ModelHTTPError propagato, 1 chiamata

def test_cancellazione_durante_la_pausa_si_propaga() -> None:
    # fallisce sempre; dormi reale; si cancella il task durante la prima pausa
    # → CancelledError, chiamate == 1

def test_senza_misura_attiva_funziona() -> None:
    # come il primo test ma fuori da misura_attese(): risposta "ok", nessuna eccezione
```

To make the request in the tests (`richiedi`), call `model.request([ModelRequest.user_text_prompt("x")], None, ModelRequestParameters())`. For streaming, use `async with model.request_stream(...) as s` and consume `s`.

- [ ] **Step 2: Run the tests and check that they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_agent_tentativi.py -q`
Expected: FAIL with `ImportError: ModelloGestito`.

- [ ] **Step 3: Implement `ModelloGestito`** in `tentativi.py` following the loop described above, and remove `ModelloLimitato` from `limiti.py`. Update the `limiti.py` module docstring, which no longer contains the wrapper.

- [ ] **Step 4: Run the tests and check that they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_agent_tentativi.py tests/test_agent_limiti.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agentic_rag/agent/tentativi.py src/agentic_rag/agent/limiti.py tests/test_agent_tentativi.py
git commit -m "feat(agent): ModelloGestito ritenta 429/5xx passando dal limitatore e misura le attese"
```

---

### Task 3: `build_model` always uses `ModelloGestito`, and the Gemini client no longer retries

**Files:**
- Modify: `src/agentic_rag/agent/model.py`
- Test: `tests/test_agent_unit.py`

**Interfaces:**
- Consumes: `ModelloGestito`, `POLITICA` (Task 2); `limitatore_per`.
- Produces: `build_model(name: str | None = None, ruolo: str = "agente") -> Model`. It always returns a `ModelloGestito`; the return type goes from `Model | str` to `Model`. `RETRY_429` is removed.

- [ ] **Step 1: Write the failing tests**

```python
def test_build_model_avvolge_sempre_con_i_tentativi() -> None:
    m = build_model("test")
    assert isinstance(m, ModelloGestito) and m.limitatore is None

def test_client_gemini_non_ritenta_da_solo(monkeypatch) -> None:
    monkeypatch.setattr(app_config, "GOOGLE_API_KEY", "chiave-finta")
    m = build_model("google:gemini-finto")
    assert isinstance(m, ModelloGestito)
    # niente doppi tentativi: li fa solo il wrapper
    assert m.wrapped.client._api_client._http_options.retry_options is None
```

If the attribute used to reach the client has a different name in pydantic-ai 2.54, adapt the path; the assertion stays the same.

- [ ] **Step 2: Run the tests and check that they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_agent_unit.py -q -k "build_model or client_gemini"`
Expected: FAIL (`"test"` returned as a string; `retry_options` set).

- [ ] **Step 3: Implement.**
  - Create `GoogleProvider(api_key=...)` without `retry_options`.
  - Always return `ModelloGestito(model, limitatore_per(ruolo, name, rpm, tpm))`.
  - Update the module docstring: the 429/5xx retries are done by the wrapper.

- [ ] **Step 4: Run the whole unit suite and check that it passes**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: PASS. The API and eval tests that monkeypatch `build_model` do not change.

- [ ] **Step 5: Commit**

```bash
git add src/agentic_rag/agent/model.py tests/test_agent_unit.py
git commit -m "fix(agent): i tentativi su 429/5xx passano dal wrapper, il client Gemini non ritenta più"
```

---

### Task 4: the eval records the provider retries and the summary reports them

**Files:**
- Modify: `src/agentic_rag/eval/runner.py` (`RisultatoDomanda`, `esegui_domanda`)
- Modify: `src/agentic_rag/eval/metriche.py` (`_base`)
- Modify: `src/agentic_rag/eval/riepilogo.py` (`efficienza`, final note of `markdown`)
- Modify: `docs/superpowers/specs/2026-10-19-harness-esperimenti-design.md`, the "Provider retries" item
- Test: `tests/test_eval_unit_runner.py`, `tests/test_eval_riepilogo.py`

**Interfaces:**
- Consumes: `ModelloGestito`, `PoliticaTentativi` (Task 2); `MisuraAttese.tentativi_falliti` (Task 1); `entro_il_tempo` (already there).
- Produces:
  - `RisultatoDomanda.tentativi_provider: int = 0`, filled from `misura.tentativi_falliti` both when the run succeeds and when it errors;
  - the `"tentativi_provider"` key in `_base`;
  - in `efficienza`, `"attesa_media_s"` (formerly `attesa_limitatore_media_s`) and `"tentativi_provider_medi"`, the latter computed with `r.get("tentativi_provider", 0)`.

- [ ] **Step 1: Write the failing tests**

`tests/test_eval_unit_runner.py` gets the regression test for the weakness. The fake `dormi` advances the fake clock **and** waits 0.3 real seconds, so the watchdog (which checks every 0.2 real seconds) really observes the pause:

```python
def test_tentativi_del_provider_non_consumano_il_tempo_di_lavoro() -> None:
    # tentativo fallito da 3 s + pausa da 2 s (politica attesa_iniziale_s=2) = 5 s di provider;
    # timeout di lavoro 4 s: prima della modifica scattava TempoScaduto
    politica = PoliticaTentativi(attesa_iniziale_s=2.0, jitter_s=0.0)
    modello = ModelloGestito(fallisce_una_volta_in_3s, None, politica, orologio=o, dormi=dormi_lento)
    with misura_attese() as m:
        risposta = asyncio.run(entro_il_tempo(richiedi(modello), 4.0, m, orologio=o))
    assert risposta.parts[0].content == "ok"
    assert m.secondi == 5.0 and m.tentativi_falliti == 1
```

In `tests/test_eval_riepilogo.py`:

```python
def test_efficienza_righe_senza_tentativi_provider() -> None:
    righe = [riga_minima()]  # helper esistente, senza la chiave "tentativi_provider"
    e = efficienza(righe, None)
    assert e["tentativi_provider_medi"] == 0 and "attesa_media_s" in e

def test_efficienza_media_dei_tentativi_provider() -> None:
    righe = [riga_minima() | {"tentativi_provider": 2}, riga_minima() | {"tentativi_provider": 0}]
    assert efficienza(righe, None)["tentativi_provider_medi"] == 1.0
```

If the test-row helper has another name, use that one: it already builds the rows with `"token_input": 1000` and `"attesa_s": 0.0`.

- [ ] **Step 2: Run the tests and check that they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_eval_unit_runner.py tests/test_eval_riepilogo.py -q`
Expected: FAIL. If Task 2 is done, the runner test may already pass, because the watchdog does not change: in that case it stays as a regression test. The summary tests fail with `KeyError: 'tentativi_provider_medi'`.

- [ ] **Step 3: Implement** the fields of the Interfaces block and update two texts.
  - **Final note of `markdown`:** replace the sentence about the client's internal retries with "Pause e tentativi falliti del provider (429/5xx, rete) sono esclusi dal tempo di lavoro e inclusi nell'attesa media."
  - **Design, "Provider retries" item:** rewrite it to say that retries are done by `ModelloGestito` (with the cadence and codes from the Global Constraints), that the duration of failed attempts and the pauses go into `attesa_s`, and that one limit remains: an attempt in progress counts as work until it fails, at most 120 s.

- [ ] **Step 4: Run the whole suite and the lint and check that they pass**

Run: `.venv/Scripts/python.exe -m pytest -q` and `.venv/Scripts/python.exe -m ruff check src tests`
Expected: PASS, no lint errors.

- [ ] **Step 5: Commit**

```bash
git add src/agentic_rag/eval/runner.py src/agentic_rag/eval/metriche.py src/agentic_rag/eval/riepilogo.py docs/superpowers/specs/2026-10-19-harness-esperimenti-design.md tests/test_eval_unit_runner.py tests/test_eval_riepilogo.py
git commit -m "feat(eval): tentativi del provider fuori dal tempo di lavoro e riportati nel riepilogo"
```

---

## Final check (manual, with the database running)

- `.venv/Scripts/python.exe -m pytest -q -m integration`: the API and eval integration tests pass.
- A real question with `python -m agentic_rag.eval --ids <an id>`: the row reports `tentativi_provider` and the duration is consistent.
- Note: changing `src/` changes the manifest hash, so experiments already started cannot be resumed. This is intended: they must be rerun.
