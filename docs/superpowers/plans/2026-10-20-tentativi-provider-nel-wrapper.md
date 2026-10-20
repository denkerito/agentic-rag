# Tentativi del provider nel wrapper del modello: piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** il tempo perso per colpa del provider (pause fra i tentativi e durata dei tentativi falliti su 429/5xx/rete) non consuma più il tempo di lavoro dell'eval, quindi un provider instabile non produce più esecuzioni `fallita_agente`.

**Architecture:** il client Gemini smette di ritentare (`GoogleProvider` senza `retry_options`). I tentativi passano in un `WrapperModel` di Pydantic AI (`ModelloGestito`), applicato sempre da `build_model` sia per l'API sia per l'eval. Il wrapper fa passare ogni tentativo dal limitatore RPM/TPM e somma in `MisuraAttese` sia la durata del tentativo fallito sia la pausa successiva. Il watchdog `entro_il_tempo` già sottrae `misura.secondi`, quindi non cambia.

**Tech Stack:** Python ≥ 3.13, pydantic-ai 2.54 (`WrapperModel`, `FunctionModel`, `ModelHTTPError`), google-genai 2.28, httpx, pytest.

**Spec:** decisioni prese in chat il 2026-10-20 (riportate sotto), da leggere insieme a `docs/superpowers/specs/2026-10-19-harness-esperimenti-design.md`. La sezione «Riletture del provider» di quel design viene aggiornata nel Task 4.

### Decisioni (dalla chat)

1. **Approccio A:** i tentativi stanno nel wrapper del modello, non nel client HTTP. Non c'è riclassificazione euristica.
2. Dal tempo di lavoro si escludono **sia la pausa sia la durata del tentativo fallito**.
3. Il comportamento vale **anche per l'API**: `build_model` è uno solo.

### Scelte mie (da confermare in revisione)

- **Cadenza:** identica a quella di oggi, cioè 5 tentativi in totale con pause di 10, 20, 40 e 60 s più un jitter fra 0 e 1 s. Si ritentano gli stessi errori di oggi: HTTP 429, 500, 502, 503 e 504, più `httpx.TimeoutException` e `httpx.ConnectError`.
- **Timeout per tentativo:** 120 s (`asyncio.wait_for`), anch'esso ritentabile. Senza questo limite, una richiesta bloccata arriverebbe al timeout HTTP di pydantic-ai (600 s) e farebbe scattare `TempoScaduto` (300 s) prima di fallire.
- **Streaming:** si ritenta solo l'apertura dello stream. Un errore dopo il primo evento si propaga com'è, altrimenti l'interfaccia dell'API vedrebbe eventi duplicati.
- **Nuovo campo `tentativi_provider`:** contiene il numero di tentativi falliti per esecuzione. Va nelle righe dell'esperimento e nell'efficienza del riepilogo, così si vede se una variante ha subito più instabilità del provider. Il campo `attesa_limitatore_media_s` diventa `attesa_media_s`, perché ora include anche le pause dei tentativi.

## Global Constraints

- Nomi, docstring, commenti e messaggi di commit in italiano, con lo stile dei file vicini.
- Codici ritentabili: `CODICI_TEMPORANEI = (429, 500, 502, 503, 504)`.
- Cadenza: `tentativi=5`, `attesa_iniziale_s=10.0`, `attesa_max_s=60.0`, `jitter_s=1.0`, `timeout_tentativo_s=120.0`.
- Le attese si sommano in `MisuraAttese` a passi di `PASSO_ATTESA_S` (1 s), già definito in `limiti.py`. Il watchdog deve vederle crescere durante la pausa, non solo alla fine.
- `asyncio.CancelledError` non si ritenta mai, perché è il modo in cui `entro_il_tempo` ferma l'agente.
- I test girano con `.venv/Scripts/python.exe -m pytest -q` (gli integration test sono esclusi di default). Il lint gira con `.venv/Scripts/python.exe -m ruff check src tests`.
- Ogni commit termina con `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Il codice e i test **non leggono** `eval/ground_truth/` (vedi AGENTS.md).

## Review Focus

1. **Errore dello stream dopo il primo evento:** non si ritenta e non duplica gli eventi. Test `test_stream_errore_dopo_il_primo_evento_non_si_ritenta` (Task 2).
2. **Cancellazione durante la pausa** (il watchdog o l'utente fermano l'indagine): il task si ferma subito e non parte nessun altro tentativo. Test `test_cancellazione_durante_la_pausa_si_propaga` (Task 2).
3. **Errori non temporanei** (400, 404 modello inesistente, `UsageLimitExceeded`, `UnexpectedModelBehavior`): si propagano al primo colpo. Test `test_da_ritentare` (Task 1) e `test_errore_non_temporaneo_non_si_ritenta` (Task 2).
4. **API senza `misura_attese()` attiva:** il wrapper funziona e non solleva eccezioni. Test `test_senza_misura_attiva_funziona` (Task 2).
5. **Esperimenti salvati prima di questa modifica,** con righe senza `tentativi_provider`: `riepilogo` non va in errore e conta 0. Test `test_efficienza_righe_senza_tentativi_provider` (Task 4).

---

### Task 1: Politica dei tentativi e attese misurate

**Files:**
- Create: `src/agentic_rag/agent/tentativi.py`
- Modify: `src/agentic_rag/agent/limiti.py`, che riceve `MisuraAttese`, l'aggiunta delle attese e il nuovo `dormi_misurato`
- Test: `tests/test_agent_tentativi.py` (nuovo), `tests/test_agent_limiti.py`

**Interfaces:**
- Produces in `limiti.py`:
  - `MisuraAttese.tentativi_falliti: int = 0`, campo nuovo accanto a `secondi`;
  - `def aggiungi_attesa(secondi: float) -> None`: somma alla misura attiva, se c'è, altrimenti non fa nulla;
  - `def conta_tentativo_fallito() -> None`;
  - `async def dormi_misurato(secondi: float, dormi: Callable[[float], Awaitable[None]] = asyncio.sleep) -> None`: dorme a passi di `PASSO_ATTESA_S` e chiama `aggiungi_attesa` dopo ogni passo.
- `Limitatore.attendi` usa `aggiungi_attesa` al posto dell'accesso diretto a `_misura`.
- Produces in `tentativi.py`:
  - `CODICI_TEMPORANEI: tuple[int, ...]`;
  - `@dataclass(frozen=True) class PoliticaTentativi`, con i campi e i default elencati nei Global Constraints;
  - `POLITICA = PoliticaTentativi()`;
  - `def pausa(politica: PoliticaTentativi, n: int, casuale: Callable[[], float] = random.random) -> float`: è la pausa dopo l'`n`-esimo tentativo fallito (n parte da 1) e vale `min(attesa_iniziale_s * 2**(n-1), attesa_max_s) + jitter_s * casuale()`;
  - `def da_ritentare(e: BaseException) -> bool`.

- [ ] **Step 1: Scrivi i test che falliscono**

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

In `tests/test_agent_limiti.py`, riusando la classe `Orologio` che c'è già:

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

- [ ] **Step 2: Lancia i test e verifica che falliscano**

Run: `.venv/Scripts/python.exe -m pytest tests/test_agent_tentativi.py tests/test_agent_limiti.py -q`
Expected: FAIL con `ModuleNotFoundError: agentic_rag.agent.tentativi` / `ImportError: dormi_misurato`.

- [ ] **Step 3: Implementa** il contenuto dell'Interfaces block.
  - In `da_ritentare`: un `ModelHTTPError` si ritenta se `status_code` è in `CODICI_TEMPORANEI`; un `genai_errors.APIError` se `code` è in `CODICI_TEMPORANEI`; si ritentano anche `httpx.TimeoutException`, `httpx.ConnectError` e `TimeoutError`.
  - `CancelledError` è una `BaseException` e deve restare esclusa.

- [ ] **Step 4: Lancia i test e verifica che passino**

Run: `.venv/Scripts/python.exe -m pytest tests/test_agent_tentativi.py tests/test_agent_limiti.py -q`
Expected: PASS (anche i 3 test del limitatore che c'erano già).

- [ ] **Step 5: Commit**

```bash
git add src/agentic_rag/agent/tentativi.py src/agentic_rag/agent/limiti.py tests/test_agent_tentativi.py tests/test_agent_limiti.py
git commit -m "feat(agent): politica dei tentativi su 429/5xx e attese misurate a passi"
```

---

### Task 2: `ModelloGestito`, il wrapper con limitatore e tentativi

**Files:**
- Modify: `src/agentic_rag/agent/tentativi.py`, dove arriva `ModelloGestito`
- Modify: `src/agentic_rag/agent/limiti.py`, da cui si rimuove `ModelloLimitato` (lo sostituisce `ModelloGestito`)
- Test: `tests/test_agent_tentativi.py`

**Interfaces:**
- Consumes: `Limitatore`, `aggiungi_attesa`, `conta_tentativo_fallito`, `dormi_misurato` (Task 1); `PoliticaTentativi`, `pausa`, `da_ritentare` (Task 1).
- Produces: `class ModelloGestito(WrapperModel)` con
  `__init__(self, wrapped: Model | KnownModelName, limitatore: Limitatore | None, politica: PoliticaTentativi = POLITICA, orologio: Callable[[], float] = time.monotonic, dormi: Callable[[float], Awaitable[None]] = asyncio.sleep, casuale: Callable[[], float] = random.random)`.
  Ridefinisce `request` e `request_stream`, con le stesse firme del `ModelloLimitato` attuale.

Ogni tentativo segue questi passi:
1. Se c'è un limitatore, chiama `await limitatore.attendi()`.
2. Prende `inizio = orologio()`.
3. Esegue la richiesta interna dentro `asyncio.wait_for(…, politica.timeout_tentativo_s)`.
4. Su un'eccezione per cui `da_ritentare` è vero chiama `aggiungi_attesa(orologio() - inizio)` e `conta_tentativo_fallito()`. Se era l'ultimo tentativo rilancia l'eccezione, altrimenti chiama `await dormi_misurato(pausa(politica, n, casuale), dormi)` e riprova.
5. Su qualsiasi altra eccezione la rilancia subito.
6. Se la richiesta riesce, registra i token nel limitatore come fa oggi.

Nello streaming il ciclo avvolge solo l'ingresso nel context manager interno: con `FunctionModel` e `GoogleModel` la risposta HTTP o il primo evento arrivano proprio lì. Dopo il `yield` non si ritenta più.

- [ ] **Step 1: Scrivi i test che falliscono**

Per i test servono:
- un `Orologio` finto, come in `tests/test_agent_limiti.py`;
- un `FunctionModel` costruito con una funzione che solleva `ModelHTTPError(503)` per i primi N tentativi e poi restituisce `ModelResponse(parts=[TextPart("ok")])`, facendo avanzare l'orologio finto di 5 s a ogni tentativo fallito;
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

Per lanciare la richiesta nei test (`richiedi`), chiama `model.request([ModelRequest.user_text_prompt("x")], None, ModelRequestParameters())`. Per lo streaming usa `async with model.request_stream(...) as s` e consuma `s`.

- [ ] **Step 2: Lancia i test e verifica che falliscano**

Run: `.venv/Scripts/python.exe -m pytest tests/test_agent_tentativi.py -q`
Expected: FAIL con `ImportError: ModelloGestito`.

- [ ] **Step 3: Implementa `ModelloGestito`** in `tentativi.py` seguendo il ciclo descritto sopra e rimuovi `ModelloLimitato` da `limiti.py`. Aggiorna la docstring del modulo `limiti.py`, che non contiene più il wrapper.

- [ ] **Step 4: Lancia i test e verifica che passino**

Run: `.venv/Scripts/python.exe -m pytest tests/test_agent_tentativi.py tests/test_agent_limiti.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agentic_rag/agent/tentativi.py src/agentic_rag/agent/limiti.py tests/test_agent_tentativi.py
git commit -m "feat(agent): ModelloGestito ritenta 429/5xx passando dal limitatore e misura le attese"
```

---

### Task 3: `build_model` usa sempre `ModelloGestito`, e il client Gemini non ritenta più

**Files:**
- Modify: `src/agentic_rag/agent/model.py`
- Test: `tests/test_agent_unit.py`

**Interfaces:**
- Consumes: `ModelloGestito`, `POLITICA` (Task 2); `limitatore_per`.
- Produces: `build_model(name: str | None = None, ruolo: str = "agente") -> Model`. Restituisce sempre un `ModelloGestito`; il tipo restituito passa da `Model | str` a `Model`. `RETRY_429` viene rimosso.

- [ ] **Step 1: Scrivi i test che falliscono**

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

Se l'attributo per arrivare al client si chiama diversamente in pydantic-ai 2.54, adatta il percorso; l'asserzione resta la stessa.

- [ ] **Step 2: Lancia i test e verifica che falliscano**

Run: `.venv/Scripts/python.exe -m pytest tests/test_agent_unit.py -q -k "build_model or client_gemini"`
Expected: FAIL (`"test"` restituito come stringa; `retry_options` impostato).

- [ ] **Step 3: Implementa.**
  - Crea `GoogleProvider(api_key=...)` senza `retry_options`.
  - Restituisci sempre `ModelloGestito(model, limitatore_per(ruolo, name, rpm, tpm))`.
  - Aggiorna la docstring del modulo: i tentativi su 429/5xx li fa il wrapper.

- [ ] **Step 4: Lancia tutta la suite unitaria e verifica che passi**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: PASS. I test di API ed eval che fanno il monkeypatch di `build_model` non cambiano.

- [ ] **Step 5: Commit**

```bash
git add src/agentic_rag/agent/model.py tests/test_agent_unit.py
git commit -m "fix(agent): i tentativi su 429/5xx passano dal wrapper, il client Gemini non ritenta più"
```

---

### Task 4: l'eval registra i tentativi del provider e il riepilogo li riporta

**Files:**
- Modify: `src/agentic_rag/eval/runner.py` (`RisultatoDomanda`, `esegui_domanda`)
- Modify: `src/agentic_rag/eval/metriche.py` (`_base`)
- Modify: `src/agentic_rag/eval/riepilogo.py` (`efficienza`, nota finale di `markdown`)
- Modify: `docs/superpowers/specs/2026-10-19-harness-esperimenti-design.md`, punto «Riletture del provider»
- Test: `tests/test_eval_unit_runner.py`, `tests/test_eval_riepilogo.py`

**Interfaces:**
- Consumes: `ModelloGestito`, `PoliticaTentativi` (Task 2); `MisuraAttese.tentativi_falliti` (Task 1); `entro_il_tempo` (già presente).
- Produces:
  - `RisultatoDomanda.tentativi_provider: int = 0`, valorizzato da `misura.tentativi_falliti` sia quando l'esecuzione riesce sia quando va in errore;
  - la chiave `"tentativi_provider"` in `_base`;
  - in `efficienza`, `"attesa_media_s"` (prima si chiamava `attesa_limitatore_media_s`) e `"tentativi_provider_medi"`, quest'ultimo calcolato con `r.get("tentativi_provider", 0)`.

- [ ] **Step 1: Scrivi i test che falliscono**

In `tests/test_eval_unit_runner.py` va il test di regressione della weakness. Il `dormi` finto fa avanzare l'orologio finto **e** aspetta 0,3 s reali, così il watchdog (che controlla ogni 0,2 s reali) osserva davvero la pausa:

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

Se l'helper delle righe di test ha un altro nome, usa quello: costruisce già le righe con `"token_input": 1000` e `"attesa_s": 0.0`.

- [ ] **Step 2: Lancia i test e verifica che falliscano**

Run: `.venv/Scripts/python.exe -m pytest tests/test_eval_unit_runner.py tests/test_eval_riepilogo.py -q`
Expected: FAIL. Se il Task 2 è fatto, il test del runner può già passare, perché il watchdog non cambia: in quel caso resta come test di regressione. I test del riepilogo falliscono con `KeyError: 'tentativi_provider_medi'`.

- [ ] **Step 3: Implementa** i campi dell'Interfaces block e aggiorna due testi.
  - **Nota finale di `markdown`:** sostituisci la frase sui tentativi interni del client con «Pause e tentativi falliti del provider (429/5xx, rete) sono esclusi dal tempo di lavoro e inclusi nell'attesa media.»
  - **Design, punto «Riletture del provider»:** riscrivilo per dire che i tentativi li fa `ModelloGestito` (con cadenza e codici dai Global Constraints), che la durata dei tentativi falliti e le pause entrano in `attesa_s` e che rimane un limite: un tentativo in corso conta come lavoro finché non fallisce, al massimo 120 s.

- [ ] **Step 4: Lancia tutta la suite e il lint e verifica che passino**

Run: `.venv/Scripts/python.exe -m pytest -q` e `.venv/Scripts/python.exe -m ruff check src tests`
Expected: PASS, nessun errore di lint.

- [ ] **Step 5: Commit**

```bash
git add src/agentic_rag/eval/runner.py src/agentic_rag/eval/metriche.py src/agentic_rag/eval/riepilogo.py docs/superpowers/specs/2026-10-19-harness-esperimenti-design.md tests/test_eval_unit_runner.py tests/test_eval_riepilogo.py
git commit -m "feat(eval): tentativi del provider fuori dal tempo di lavoro e riportati nel riepilogo"
```

---

## Verifica finale (manuale, con il database acceso)

- `.venv/Scripts/python.exe -m pytest -q -m integration`: gli integration test di API ed eval passano.
- Una domanda reale con `python -m agentic_rag.eval --ids <un id>`: la riga riporta `tentativi_provider` e la durata è coerente.
- Nota: cambiando `src/`, l'hash del manifesto cambia e gli esperimenti già avviati non si possono riprendere. È voluto: vanno rieseguiti.
