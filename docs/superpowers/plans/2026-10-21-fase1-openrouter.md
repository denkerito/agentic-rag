# Fase 1 — Passaggio a OpenRouter: piano di implementazione

> **Per chi esegue:** superpowers:executing-plans (consigliato, in questa sessione) oppure superpowers:subagent-driven-development, un task alla volta. I passi usano le checkbox.

**Obiettivo:** agente e giudice girano su Claude tramite OpenRouter. L'harness registra il costo reale, non chiude esecuzioni senza verdetto del giudice e si ferma sugli errori di credito o di chiave.

**Architettura:** `build_model` riconosce il prefisso `openrouter:` e costruisce un `OpenRouterModel`, sempre avvolto in `ModelloGestito` come oggi. Il modello ha client OpenAI senza tentativi propri, cache e provider fissato. L'harness legge costo e token di cache dalle risposte catturate. Due nuovi esiti proteggono l'esperimento:
- lo stato `errore_giudice`, che lascia la combinazione aperta;
- l'eccezione `ErroreFatale`, che ferma l'esecuzione.

**Stack:** Python 3.13, pydantic-ai-slim ≥ 2.59 (extra `google`, `openrouter`), pytest, ruff.

**Spec:** `docs/superpowers/specs/2026-10-21-percorso-valutazione-openrouter-design.md`, Fase 1.

## Contesto

Il modello definitivo sarà Claude Haiku 5.5, con Sonnet 5.5 come giudice, entrambi via OpenRouter. Oggi il codice parla solo con Gemini. La lettura dell'harness ha mostrato tre lacune che renderebbero inaffidabile un esperimento a pagamento:
1. **Costo:** non c'è modo di vedere quanto costa un'esecuzione (`PREZZI` è vuoto).
2. **Giudice:** se fallisce, l'esecuzione resta "completata" senza verdetto e il Task Success Rate ignora il giudice.
3. **Credito o chiave:** un 401/402/403 chiude la combinazione come `fallita_agente`. Con il credito esaurito a metà, il resto dell'esperimento diventerebbe una serie di finti insuccessi.

Inoltre, con il client OpenAI-compatibile gli errori di rete arrivano come `ModelAPIError`, che `ModelloGestito` non ritenta. In questa fase non si fa nessuna chiamata a pagamento: la prima è la prova breve della fase 2.

## Vincoli globali

- **Modelli:** agente `openrouter:anthropic/claude-haiku-5.5`, giudice `openrouter:anthropic/claude-sonnet-5.5`. Il supporto `google:` resta.
- **Provider OpenRouter fissato:** `{"order": ["anthropic"], "allow_fallbacks": False}`.
- **Effort:** agente al default del modello (nessuna impostazione), giudice `medium`. `max_tokens` = 16 000 per entrambi.
- **Cache:** istruzioni, definizioni dei tool e ultimo messaggio (TTL 5 min).
- **Tentativi:** solo in `ModelloGestito`; il client OpenAI ha `max_retries=0`.
- **Embedding:** invariati (Gemini, `GOOGLE_API_KEY`).
- **Errori fatali:** HTTP 401, 402, 403.
- **Manifesto:** provider, effort, cache e `max_tokens` sono costanti in `src/` e non variabili d'ambiente. L'hash di `src/` nel manifesto le copre, quindi la voce 7 della spec non richiede codice.
- **Ground truth:** non si apre nessun file di `eval/ground_truth/`; i test usano ground truth sintetici, come oggi.
- **Git:** branch `feat/openrouter-fase1`, un commit per task, messaggi in stile `tipo(area): …` in italiano.

## Review Focus

1. **Credito esaurito a metà esperimento (402):** l'esperimento si ferma, la combinazione in corso resta aperta e la ripresa la riesegue senza duplicati (test nel Task 6).
2. **Giudice che fallisce sempre** (ad esempio un 400 per un parametro non supportato): nessuna combinazione si chiude senza verdetto, e il riepilogo dichiara l'esperimento non valido invece di gonfiare il Task Success Rate (Task 7).
3. **Righe di esperimenti salvati prima di questi campi** (Gemini): il riepilogo non si rompe e mostra n/d (Task 8).
4. **Disconnessione del client OpenAI a metà richiesta:** ritentata dal wrapper, non conta come fallimento (Task 5).
5. **`OPENROUTER_API_KEY` mancante:** messaggio chiaro prima di partire, non decine di esecuzioni in errore (Task 2 e Task 4).

---

### Task 1: branch, documenti e aggiornamento di pydantic-ai

**File:** `pyproject.toml`; eventuali adattamenti in `tests/test_agent_unit.py`.

- [ ] `git switch -c feat/openrouter-fase1`. Copiare questo piano in `docs/superpowers/plans/2026-10-21-fase1-openrouter.md`. Commit della spec e del piano: `docs: percorso di valutazione con OpenRouter e piano della fase 1`.
- [ ] In `pyproject.toml`, `"pydantic-ai-slim[google]"` diventa `"pydantic-ai-slim[google,openrouter]>=2.59"`. Poi `.venv/Scripts/python.exe -m pip install -e ".[dev]"`. Atteso: `import openai` funziona.
- [ ] `.venv/Scripts/python.exe -m pytest` e `-m integration` con il DB acceso. Atteso: 178 + 75 verdi. Se `test_client_gemini_non_ritenta_da_solo` si rompe per attributi privati cambiati, si adatta il percorso dell'ispezione mantenendo l'asserzione: il client Gemini non ha `retry_options`.
- [ ] Commit: `build: pydantic-ai 2.59 con supporto OpenRouter`.

### Task 2: OpenRouter in `build_model`

**File:** `src/agentic_rag/config.py`, `src/agentic_rag/agent/config.py`, `src/agentic_rag/agent/model.py`, `.env.example`, `tests/test_agent_unit.py`.

**Produce:**
- `config.OPENROUTER_API_KEY: str` (env `OPENROUTER_API_KEY`, default `""`).
- In `agent_config`:
  - default di `AGENT_MODEL` = `"openrouter:anthropic/claude-haiku-5.5"`;
  - `JUDGE_MODEL: str` = env `JUDGE_MODEL`, default `"openrouter:anthropic/claude-sonnet-5.5"`;
  - `OPENROUTER_PROVIDER = {"order": ["anthropic"], "allow_fallbacks": False}`;
  - `EFFORT: dict[str, str | None] = {"agente": None, "giudice": "medium"}`;
  - `MAX_TOKENS_RISPOSTA = 16_000`.
- In `model`:
  - `OPENROUTER_PREFIX = "openrouter:"`;
  - `impostazioni_openrouter(ruolo: str) -> OpenRouterModelSettings`;
  - `build_model(name, ruolo)` con la firma invariata.

- [ ] **Test che falliscono** in `tests/test_agent_unit.py`:
  - `test_impostazioni_openrouter`, sul ruolo `"agente"`:
    - le tre chiavi `openrouter_cache_instructions`, `openrouter_cache_tool_definitions` e `openrouter_cache_messages` sono vere;
    - `openrouter_provider == {"order": ["anthropic"], "allow_fallbacks": False}`;
    - `openrouter_usage == {"include": True}`;
    - `max_tokens == 16_000`;
    - `"openrouter_reasoning" not in` le impostazioni.
  - Sempre in `test_impostazioni_openrouter`, sul ruolo `"giudice"`: `["openrouter_reasoning"] == {"effort": "medium"}`.
  - `test_client_openrouter_non_ritenta_da_solo`, con `monkeypatch` su `app_config.OPENROUTER_API_KEY = "chiave-finta"`:
    - `build_model("openrouter:anthropic/claude-haiku-5.5")` è un `ModelloGestito` che avvolge un `OpenRouterModel`;
    - `model_name == "anthropic/claude-haiku-5.5"`;
    - il client OpenAI del modello ha `max_retries == 0`.
  - `test_openrouter_senza_chiave`: con la chiave vuota, `pytest.raises(SystemExit, match="OPENROUTER_API_KEY")`.
- [ ] Eseguire: `pytest tests/test_agent_unit.py -k openrouter`. Atteso: FAIL (import mancante).
- [ ] **Implementazione in `build_model`:**
  - il ramo `openrouter:` costruisce `AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=…, max_retries=0)` e lo passa a `OpenRouterProvider(openai_client=…)`;
  - poi crea `OpenRouterModel(nome senza prefisso, provider=…, settings=impostazioni_openrouter(ruolo))`;
  - senza chiave solleva `SystemExit("OPENROUTER_API_KEY non impostata (vedi .env.example)")`. È lo stesso schema di `open_session` per `DATABASE_URL_AGENT`, che `esegui_domanda` già traduce in errore di configurazione.
- [ ] Aggiornare `.env.example`: `OPENROUTER_API_KEY=`, i nuovi default di `AGENT_MODEL` e `JUDGE_MODEL` commentati, e una nota che `GOOGLE_API_KEY` serve agli embedding.
- [ ] Eseguire: `pytest tests/test_agent_unit.py`. Atteso: PASS.
- [ ] Commit: `feat(agent): modelli OpenRouter con cache e provider fissato, tentativi nel wrapper`.

### Task 3: giudice su Sonnet

**File:** `src/agentic_rag/eval/giudice.py`, `src/agentic_rag/eval/esperimento.py` (`cmd_esegui`, help di `--judge-model`), `src/agentic_rag/eval/__main__.py` (help e `meta["giudice"]`), nuovo `tests/test_eval_giudice.py`.

**Usa:** `agent_config.JUDGE_MODEL` (Task 2).

- [ ] **Test che fallisce:** `test_il_giudice_usa_judge_model_senza_temperatura`.
  - `monkeypatch` su `giudice.build_model` con una funzione che registra `(name, ruolo)` e restituisce un `FunctionModel`.
  - Il `FunctionModel` salva `info.model_settings` e risponde con la chiamata di output `{"verdetto": "corretta", "motivazione": "m"}`.
  - Asserire: `name == agent_config.JUDGE_MODEL`, `ruolo == "giudice"`, `(model_settings or {}).get("temperature") is None`.
- [ ] Eseguire. Atteso: FAIL.
- [ ] **Implementazione:**
  - `giudica` usa `build_model(model or agent_config.JUDGE_MODEL, ruolo="giudice")` e toglie `model_settings=ModelSettings(temperature=0)`;
  - le due CLI usano `args.judge_model or agent_config.JUDGE_MODEL` quando `--judge` è attivo;
  - i testi di help indicano il nuovo default.
- [ ] Eseguire `pytest`. Atteso: PASS. Commit: `feat(eval): giudice su JUDGE_MODEL, senza temperatura`.

### Task 4: controllo dell'ambiente per provider

**File:** `src/agentic_rag/eval/ambiente.py`, chiamate in `esperimento.py` e `__main__.py`, `tests/test_eval_ambiente.py`.

**Produce:** `controlla_ambiente(modelli: Sequence[str] = (), db_url: str | None = None, google_key: str | None = None, openrouter_key: str | None = None) -> list[str]`. Il parametro `api_key` diventa `google_key`.

- [ ] **Test che fallisce:** `test_chiave_openrouter_richiesta_solo_se_serve`.
  - Con `["openrouter:anthropic/claude-haiku-5.5"]`, `db_url=""`, `google_key="k"` e `openrouter_key=""`, un problema contiene `OPENROUTER_API_KEY`.
  - Con `["google:m"]`, nessun problema contiene `OPENROUTER_API_KEY`.
  - I due test esistenti si aggiornano a `google_key=`.
- [ ] **Implementazione:**
  - `GOOGLE_API_KEY` resta sempre richiesta, con il messaggio "…(serve agli embedding della ricerca semantica)";
  - `OPENROUTER_API_KEY` è richiesta se un modello inizia con `openrouter:`;
  - `cmd_esegui` passa i modelli delle varianti più il giudice;
  - la CLI a batteria passa `args.model or AGENT_MODEL` più il giudice se `--judge`.
- [ ] Eseguire `pytest`. Atteso: PASS. Commit: `feat(eval): il controllo dell'ambiente verifica la chiave del provider usato`.

### Task 5: ritentare gli errori di trasporto del client OpenAI

**File:** `src/agentic_rag/agent/tentativi.py` (`da_ritentare` e commento di `ERRORI_RETE`), `tests/test_agent_tentativi.py`.

- [ ] **Test che fallisce:** in `test_da_ritentare` aggiungere:
  - `assert da_ritentare(ModelAPIError("openrouter:m", "Connection error."))`;
  - `assert not da_ritentare(ModelHTTPError(status_code=402, model_name="m"))`.
- [ ] **Implementazione:** in `da_ritentare`, dopo il ramo `ModelHTTPError` (che è una sottoclasse e va controllata prima), `isinstance(e, ModelAPIError)` restituisce `True`. Sono gli errori di connessione e i corpi senza completamento che pydantic-ai segnala come transitori.
- [ ] Eseguire `pytest tests/test_agent_tentativi.py`. Atteso: PASS. Commit: `fix(agent): ModelloGestito ritenta gli errori di trasporto del client OpenAI`.

### Task 6: gli errori fatali fermano l'esecuzione

**File:** `src/agentic_rag/eval/runner.py`, `esperimento.py` (`cmd_esegui`), `__main__.py`, `tests/test_eval_unit_runner.py`, `tests/test_eval_esperimento.py`, `tests/test_eval_integration.py`.

**Produce** in `runner.py`:
- `CODICI_FATALI = (401, 402, 403)`;
- `class ErroreFatale(Exception)`, con messaggio `nome_errore(e)`, ad esempio `"ModelHTTPError 402"`;
- `errore_fatale(e: BaseException) -> bool`, vero per un `ModelHTTPError` con codice in `CODICI_FATALI`.

- [ ] **Test che falliscono:**
  - **Unit:**
    - `errore_fatale` è vero per `ModelHTTPError` 401, 402 e 403, falso per 400, 429 e 503;
    - `errore_di_infrastruttura(ModelHTTPError(402, …))` resta falso.
  - **Unit, esperimento:**
    - un eseguitore finto solleva `ErroreFatale` alla seconda combinazione: `pytest.raises(ErroreFatale)` attorno a `esegui_esperimento`, e il JSONL ha esattamente 1 riga;
    - la ripresa con un eseguitore che risponde sempre ok chiude tutte le combinazioni, senza duplicati, e la seconda combinazione ha `tentativo == 1`.
  - **Integrazione:**
    - un `FunctionModel` che solleva `ModelHTTPError(402, "m")` fa sollevare `ErroreFatale` a `esegui_domanda` (`build_model` sostituito come negli altri test);
    - lo stesso vale con il giudice (`giudice.build_model` sostituito) che risponde 402.
- [ ] **Implementazione:**
  - in `esegui_domanda`, nell'`except` della run e nel ciclo del giudice: `if errore_fatale(e): raise ErroreFatale(nome_errore(e)) from e`. La connessione si chiude comunque nel `finally`.
  - `cmd_esegui` intercetta `ErroreFatale` e stampa: "Fermato per {e}: credito esaurito o chiave non valida. Le esecuzioni concluse sono salvate: ricarica o correggi la chiave e rilancia `esegui --etichetta X`." Poi termina senza riepilogo.
  - La CLI a batteria la tratta come un `KeyboardInterrupt` (`interrotta=True` più messaggio).
- [ ] Eseguire `pytest` e `pytest -m integration`. Atteso: PASS. Commit: `fix(eval): credito esaurito o chiave non valida fermano l'esperimento`.

### Task 7: un giudice senza verdetto lascia aperta la combinazione

**File:** `runner.py` (`Stato`, `esegui_domanda`), `riepilogo.py` (`riepiloga`, `markdown`), test di runner, esperimento, riepilogo e integrazione.

**Produce:** `Stato` include `"errore_giudice"`, non presente in `STATI_CHIUSI`. Il riepilogo aggiunge per ogni variante il campo `"errori_giudice": int`.

- [ ] **Test che falliscono:**
  - **Integrazione:** un giudice `FunctionModel` che fallisce sempre (solleva `ModelHTTPError(400, "m")`) fa restituire a `esegui_domanda` lo stato `"errore_giudice"` con esito `"errore"`, mantenendo risposta, token e rifiuti.
  - **Esperimento:** un eseguitore che restituisce `errore_giudice` per una combinazione due volte, poi ok, produce le righe (1, errore_giudice), (2, errore_giudice) e (3, completata). È lo stesso schema del test sull'infrastruttura.
  - **Riepilogo:** con una riga `errore_giudice` la combinazione non è chiusa e `riepiloga(...)["varianti"]["con"]["errori_giudice"] == 1`. Se tutte le esecuzioni di una variante sono in `errore_giudice`, `valido` è falso.
- [ ] **Implementazione:**
  - in `esegui_domanda`, se il giudice è acceso, la domanda ha `risposta_attesa` e dopo `TENTATIVI_GIUDICE` non c'è verdetto, restituisce lo stato `errore_giudice` con tutti i dati dell'esecuzione;
  - l'esperimento non cambia: gli stati non chiusi restano aperti e vengono ritentati;
  - la CLI a batteria non riesegue e mostra `errore_giudice` come oggi;
  - la riga "Esecuzioni" del Markdown riporta il conteggio.
- [ ] Eseguire `pytest` e `pytest -m integration`. Atteso: PASS. Commit: `fix(eval): un'esecuzione senza verdetto del giudice resta da rifare`.

### Task 8: costo reale e cache nel riepilogo

**File:** `runner.py`, `metriche.py` (`_base`), `riepilogo.py` (togliere `PREZZI`; `efficienza`, `riepiloga`, `markdown`), test di runner, riepilogo e integrazione.

**Produce:**
- `costo_risposte(messaggi: Sequence[ModelMessage]) -> float | None`: somma di `provider_details["cost"]` sulle `ModelResponse`; `None` se nessuna risposta ha un costo, come succede con Gemini o i modelli finti.
- Nuovi campi di `RisultatoDomanda`: `costo_usd: float | None = None`, `costo_giudice_usd: float | None = None`, `token_cache_lettura: int = 0`, `token_cache_scrittura: int = 0`.
- `efficienza(righe)`: il parametro `modello` sparisce. Calcola:
  - `costo_medio_usd` e `costo_giudice_medio_usd`: media sulle righe con un costo, `None` se nessuna lo ha;
  - `quota_input_da_cache`: Σ `token_cache_lettura` / Σ `token_input`, `None` se l'input è 0.
- `riepiloga`: per variante e in totale, `costo_totale_usd` su **tutte** le righe, compresi i tentativi falliti e gli errori di infrastruttura, perché anche quelli si pagano.

- [ ] **Test che falliscono:**
  - **Unit:** `costo_risposte` con due `ModelResponse` (costo 0,001 e 0,002) e una `ModelRequest` dà `pytest.approx(0.003)`; senza costi dà `None`.
  - **Riepilogo:**
    - il totale include anche una riga `errore_infrastruttura` con un costo;
    - righe senza i nuovi campi danno costo `None` e nessuna eccezione;
    - 500 token letti dalla cache su 1000 di input danno una quota di 0,5;
    - si aggiornano le chiamate esistenti a `efficienza(righe, None)`.
  - **Integrazione:** un `FunctionModel` che restituisce `ModelResponse(..., provider_details={"cost": 0.001})` produce una riga pubblica con `costo_usd == approx(0.001 × numero di risposte)`.
- [ ] **Implementazione:**
  - in `esegui_domanda` (riuscita e fallita) il costo viene da `costo_risposte(messaggi)` e i token di cache da `usage.cache_read_tokens` e `usage.cache_write_tokens`;
  - ogni tentativo del giudice gira dentro un proprio `capture_run_messages()` e il suo costo si somma;
  - `_base` aggiunge i quattro campi alla riga;
  - le righe vecchie si leggono con `r.get(...)`;
  - il Markdown aggiunge in testa la riga "costo: X $ (agente A $, giudice G $) su N esecuzioni" oppure "n/d".
- [ ] Eseguire `pytest` e `pytest -m integration`. Atteso: PASS. Commit: `feat(eval): costo reale da OpenRouter e quota di input da cache nel riepilogo`.

### Task 9: documentazione e verifica finale

**File:** `README.md`.
- Architettura: "LLM (Gemini)" diventa Claude via OpenRouter.
- Requisiti dell'avvio locale: `OPENROUTER_API_KEY`, più `GOOGLE_API_KEY` per gli embedding.
- Variabili principali: `JUDGE_MODEL`.
- Sezione Test e valutazione: il giudice di default e la riga del costo.

- [ ] Aggiornare il README.
- [ ] Verifica completa, senza chiamate a pagamento:
  - `.venv/Scripts/python.exe -m pytest`: tutto verde.
  - `.venv/Scripts/python.exe -m pytest -m integration`, con il DB acceso: tutto verde.
  - `.venv/Scripts/python.exe -m ruff check src tests`: "All checks passed!".
  - `.venv/Scripts/python.exe -m agentic_rag.eval --dry-run`: stampa solo la struttura, come oggi.
  - con `OPENROUTER_API_KEY` impostata, `python -c "from agentic_rag.agent.model import build_model; print(build_model(), build_model(ruolo='giudice'))"` costruisce i modelli senza chiamare la rete.
- [ ] Commit: `docs: README per Claude via OpenRouter`. Branch e PR restano da decidere dopo la revisione.

## Verifica end-to-end

In questa fase tutta la verifica è locale e gratuita: test unitari, test di integrazione sul DB reale con modelli finti, `ruff` e dry-run. La prima chiamata reale a OpenRouter è la prova breve della fase 2, che controlla sul servizio vero ciò che qui si prova con i finti:
- cache letta dalla seconda richiesta;
- costo uguale a quello mostrato da OpenRouter;
- verdetto presente in ogni esecuzione;
- arresto pulito con una chiave non valida.
