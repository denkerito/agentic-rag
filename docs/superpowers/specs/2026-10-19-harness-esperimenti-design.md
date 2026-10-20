# Design: harness per esperimenti (ripresa, metriche, statistica)

Stato: approvato · 2026-10-19

## Contesto e perché

L'harness di valutazione oggi esegue **una batteria alla volta** (`python -m agentic_rag.eval`).

**Cosa è andato storto:** l'esperimento sull'ablazione della ricerca semantica (10 batterie) è morto due volte a metà, perdendo tutto ciò che aveva già eseguito. In parallelo, Gemini restituiva errori 5xx che si confondevano con i fallimenti dell'agente.

**Cosa serve:** due esperimenti di ore, che arrivino in fondo e producano numeri difendibili.
1. **Esperimento decisionale:** tenere o no la ricerca semantica. Si esegue dopo la scelta del modello definitivo, ancora da valutare.
2. **Benchmark finale:** le metriche da citare nel CV, a progetto congelato e su un test set nuovo scritto dall'utente.

**Obiettivo:** un harness che
- tratti l'esperimento (varianti × ripetizioni × domande) come unità;
- salvi ogni esecuzione appena conclusa e riprenda da dove si era fermato;
- separi gli errori di infrastruttura dai fallimenti dell'agente;
- calcoli un piccolo insieme di metriche con nomi standard e intervalli di confidenza.

## Obiettivi

1. **Ripresa:** un'interruzione costa al massimo l'esecuzione in corso.
2. **Riproducibilità:** il manifesto lega l'esperimento al codice e al ground truth; la ripresa rifiuta se sono cambiati.
3. **Varianti generiche:** configurazioni (modello, ricerca semantica), così lo stesso comando serve per l'ablazione **e** per confrontare modelli.
4. **Errori di infrastruttura** gestiti con la politica B e tre salvaguardie (sotto).
5. **Metriche:** quelle scelte (sotto), con denominatori espliciti, intervalli al 95% e confronti appaiati.
6. **Limitatore di richieste** opzionale e indipendente dal provider, che misura sempre le attese (approccio 1).
7. **Validazione del giudice** con Cohen's κ su etichette umane, senza che l'assistente veda il ground truth.

## Non obiettivi

- Il contenuto del nuovo test set: lo scrive l'utente. L'harness funziona con qualsiasi set conforme allo schema attuale.
- Esecuzione in parallelo, dashboard, interfaccia web dei risultati.
- Limitatore adattivo o lettura delle intestazioni di rate limit dei provider.
- Modifiche al criterio di `ok` (`calcola_esito`): resta quello del protocollo dell'ablazione.
- Metriche escluse: Citation Precision (rumorosa), Numeric Groundedness (troppi falsi positivi, rimandata), Recall@k/MRR/nDCG (richiedono un benchmark di retrieval separato), pass@k.

## Anti-obiettivi

- Scegliere o ridefinire le metriche **dopo** aver visto i risultati.
- Un risultato migliore della realtà perché sono saltate le domande difficili (vedi salvaguardie).
- Contenuti del ground truth nei file pubblici, o letti dall'assistente (`AGENTS.md`).

## Concetti

- **Combinazione:** (variante, ripetizione, domanda). È l'unità di lavoro, di ripresa e di esclusione.
- **Esecuzione:** un tentativo di una combinazione. Può concludersi in tre modi:
  - `completata`: c'è un esito `ok`/`ko`/`nd`;
  - `fallita_agente`: limite di richieste, risposta non valida dopo i tentativi, timeout sul tempo di lavoro;
  - `errore_infrastruttura`: rete, 429, 5xx dopo i tentativi dell'SDK.
- Una combinazione è **chiusa** quando ha un'esecuzione `completata` o `fallita_agente`. Con solo `errore_infrastruttura` resta **aperta**.

## Interfaccia (CLI)

```bash
# crea l'esperimento
python -m agentic_rag.eval.esperimento esegui --etichetta esp-ricerca-a \
    --variante con:semantica=1 --variante senza:semantica=0 \
    --ripetizioni 5 --judge [--judge-model M] [--pausa 5] [--tentativi-finali 2] \
    [--criterio "task_success_rate:con-senza>=10"]

# lo riprende (parametri presi dal manifesto: con --variante, --ids, --criterio o --timeout rifiuta)
python -m agentic_rag.eval.esperimento esegui --etichetta esp-ricerca-a [--pausa 5] [--tentativi-finali 2]

python -m agentic_rag.eval.esperimento riepilogo --etichetta esp-ricerca-a
python -m agentic_rag.eval.esperimento etichette --etichetta esp-ricerca-a --campione 30
python -m agentic_rag.eval.esperimento kappa --etichetta esp-ricerca-a
```

- **Chiavi di una variante:** `modello` (default `AGENT_MODEL`) e `semantica` (default 1).
- **Giudice:** unico per tutto l'esperimento, perché tutte le varianti devono essere giudicate allo stesso modo.
- La CLI attuale `python -m agentic_rag.eval` resta per le prove veloci. `eval.confronta` viene rimosso: lo sostituisce `riepilogo`.

## Persistenza

| Cosa | Dove | Contenuto |
|---|---|---|
| Manifesto | `eval/reports/esperimenti/<etichetta>/manifest.json` | Vedi sotto |
| Esecuzioni pubbliche | `.../<etichetta>/esecuzioni.jsonl` | Una riga per esecuzione, aggiunta e scritta su disco appena conclusa: chiave della combinazione, tentativo, stato, esito, metriche per esecuzione (solo conteggi e frazioni, come `riga_pubblica`), utilizzo, tempi, errore |
| Esecuzioni private | `eval/reports/private/esperimenti/<etichetta>/esecuzioni.jsonl` | In più: domanda, risposta attesa, dettagli (già ignorata da git) |
| Riepilogo | `.../<etichetta>/riepilogo.md` + `riepilogo.json` | Generato da `riepilogo`, mai a mano |
| Foglio di etichettatura | `eval/reports/private/esperimenti/<etichetta>/etichette.csv` | Privato |

**Contenuto del manifesto** (scritto alla creazione, verificato a ogni ripresa):
- etichetta, data di creazione;
- **hash dell'albero `src/` al commit corrente** (`git rev-parse HEAD:src`). Rifiuta se `src/` ha modifiche non committate; le modifiche fuori da `src/`, come i report o il README, non bloccano;
- varianti, ripetizioni, modello del giudice, criterio;
- limiti: `AGENT_MAX_REQUESTS`, timeout, `SEARCH_MAX_DISTANCE`, `ELENCO_PER_PAGINA`, `TESTO_MAX_K`, RPM/TPM;
- **sha256 dei file del ground truth** (solo l'hash) e l'elenco degli ID delle domande.

Se alla ripresa qualcosa non coincide, il comando si ferma e indica *quali chiavi* differiscono, senza mostrare valori del ground truth.

## Esecuzione

1. **Ordine:** per ogni ripetizione, per ogni variante, per ogni domanda. Le varianti sono alternate, così un periodo in cui il provider va male colpisce tutte allo stesso modo.
2. **Ripresa:** si saltano le combinazioni chiuse.
3. **Errori di infrastruttura (politica B con salvaguardie):**
   - durante il ciclo principale: un nuovo tentativo immediato dopo la pausa, come oggi;
   - **salvaguardia 1:** finito il ciclo, un passaggio finale ritenta le combinazioni ancora aperte, fino a `--tentativi-finali` volte (default 2). Le combinazioni rimaste aperte sono **escluse** e riportate nel riepilogo.
4. **Timeout:** si misura sul **tempo di lavoro**, cioè tempo reale meno le attese del limitatore, con il default attuale di 300 s.
   - Scattare è un fallimento dell'agente (`fallita_agente`), con una propria eccezione `TempoScaduto`.
   - Si corregge `errore_di_infrastruttura` in `src/agentic_rag/eval/runner.py`, che oggi tratta ogni `TimeoutError` come infrastruttura. I timeout di rete (`httpx.TimeoutException`) restano infrastruttura.
5. **Dati raccolti per ogni esecuzione,** in aggiunta a quelli attuali di `RisultatoDomanda`:
   - token in ingresso e in uscita (`result.usage`);
   - secondi di attesa del limitatore;
   - tempo di lavoro;
   - **risposte rifiutate dal validatore, per motivo**: si contano i `RetryPromptPart` del tool di output in `result.all_messages()`. Il motivo si riconosce da costanti definite in `src/agentic_rag/agent/agent.py` accanto a `check_risposta`: fonti mai viste, numero senza fonti, causa documentata senza documento;
   - **documenti recuperati**: `doc_ids` dalla traccia di `cerca_testo` e `cerca_semantica`, più i `doc_id` aperti con `apri_documento`. `elenca_documenti` non conta: elenca, non recupera.

## Limitatore di richieste (approccio 1)

- **Struttura:** un involucro `WrapperModel` di Pydantic AI attorno a qualsiasi modello, applicato in `build_model` (`src/agentic_rag/agent/model.py`). Vale per qualsiasi provider.
- **Configurazione:** `AGENT_RPM`, `AGENT_TPM`, `JUDGE_RPM`, `JUDGE_TPM`. **Non impostate significa limitatore spento**, ma il tempo di attesa (zero) viene comunque misurato.
- **Funzionamento:** finestra scorrevole di 60 s.
  - Prima di una richiesta attende se si supererebbe l'RPM, o se i token usati nella finestra hanno raggiunto il TPM (conteggiati dall'utilizzo reale delle risposte).
- **Stato:** un'istanza per nome di modello, a livello di processo. `build_model` viene chiamato a ogni domanda e la finestra non deve ripartire da zero.
- **Riletture del provider:** 429, 5xx (500, 502, 503, 504) ed errori di rete li ritenta `ModelloGestito` (`src/agentic_rag/agent/tentativi.py`), non il client del provider: 5 tentativi, pause di 10, 20, 40, 60 s più un jitter fino a 1 s, timeout di 120 s per tentativo. Ogni tentativo passa dal limitatore. La durata dei tentativi falliti e le pause entrano in `attesa_s` (escluse dal tempo di lavoro); `tentativi_provider` conta i tentativi falliti per esecuzione. Limite noto: un tentativo in corso conta come lavoro finché non fallisce, al massimo 120 s. Gli altri provider mantengono anche i `max_retries` del proprio SDK.

## Metriche

Ogni metrica si calcola **solo dove si applica**, e il riepilogo indica sempre il denominatore.

| # | Metrica | Definizione | Si applica a |
|---|---|---|---|
| 1 | **Task Success Rate** | Esecuzioni con esito `ok` ÷ esecuzioni chiuse (`fallita_agente` conta come insuccesso) | tutte le domande |
| 2 | **Answer Accuracy (LLM-as-a-judge)** | Verdetti `corretta` ÷ esecuzioni giudicate; si riporta anche la quota `parziale`. Un giudizio fallito dopo i tentativi è escluso e contato | domande con risposta attesa, giudice acceso |
| 3 | **pass^k** (k=3) | Media sulle domande di C(c,k)/C(n,k), con n esecuzioni chiuse e c riuscite | domande con n ≥ k |
| 4 | **Source Citation Recall** | Media di `id_trovati / id_attesi` (`MetricheFonti`) | domande con ID attesi |
| 5 | **Numeric Exact Match Recall** | Media di `MetricheNumeri.recall` | domande con query attesa applicabile |
| 6a | **False Acceptance Rate** | Esecuzioni con `causa_documentata=true` ÷ esecuzioni su domande con causa non documentata | modalità `onesta` e `non_rispondibile` |
| 6b | **False Abstention Rate** | Esecuzioni con `causa_documentata=false` ÷ esecuzioni su domande con causa documentata | modalità `normale` con almeno un `DOC-*`/`CTR-*` tra gli ID attesi (ricavato dalla struttura) |
| 7 | **Guardrail Intervention Rate** | Esecuzioni con almeno un rifiuto del validatore ÷ esecuzioni; più il totale dei rifiuti per motivo | tutte |
| 8 | **Session Evidence Recall** | Documenti attesi (`DOC-*`/`CTR-*`) recuperati ÷ documenti attesi | domande con documenti attesi |
| + | **Efficienza** | Token in ingresso e uscita, richieste e chiamate a tool per indagine (medie); tempo di lavoro p50/p95; costo per indagine da una tabella di prezzi per modello in configurazione (n/d se il modello non è in tabella) | esecuzioni chiuse |

Nel riepilogo ogni metrica è riportata **per variante**, **per modalità** e nel **totale**.

## Statistica

- **Aggregazione:** prima per domanda (media delle sue esecuzioni), poi media sulle domande, che pesano tutte allo stesso modo.
- **Intervallo al 95%:** bootstrap percentile ricampionando le domande, B = 2000, con seme fisso per avere riepiloghi riproducibili.
- **Confronto tra varianti:** bootstrap appaiato sulla differenza, calcolato **solo sulle combinazioni chiuse in entrambe** le varianti (salvaguardia 2).
- **Verdetto pre-registrato:** se il manifesto contiene un criterio, il riepilogo lo valuta sulle combinazioni appaiate.
  - Formato: metrica, variante, riferimento, soglia in punti.
  - Per l'ablazione: Task Success Rate, `con` − `senza` ≥ 10 punti. Il verdetto usa la stima puntuale come da protocollo; l'intervallo è mostrato accanto.
- **Validità (salvaguardia 3):** l'esperimento è dichiarato **non valido** e non si emette nessun verdetto se:
  - una variante ha più del 10% di combinazioni escluse, oppure
  - la quota di escluse differisce tra due varianti di più di 5 punti.

  Le escluse sono sempre elencate (variante, ripetizione, ID domanda).

## Validazione del giudice (Cohen's κ)

- **`etichette`:** estrae un campione stratificato per modalità e variante, con seme fisso, tra le esecuzioni giudicate. Lo scrive nel CSV privato: domanda, risposta attesa, conclusione, causa documentata e limiti dell'agente, e una colonna vuota `etichetta_umana`.
  - **Il verdetto del giudice non è nel foglio:** l'etichettatura è alla cieca.
  - Lo compila l'utente.
- **`kappa`:** confronta le etichette umane con i verdetti del giudice e calcola:
  - κ di Cohen sulle tre classi;
  - κ sulla versione binaria (corretta / non corretta);
  - accordo percentuale.

  Scrive **solo questi numeri** nel riepilogo pubblico. L'assistente non apre il CSV.

## Modifiche all'esistente

| File | Modifica |
|---|---|
| `src/agentic_rag/eval/runner.py` | Riusa `esegui_domanda` e lo estende con timeout sul tempo di lavoro, raccolta di token/attese/rifiuti/documenti recuperati e classificazione corretta del timeout. La CLI a batteria continua a usarlo |
| `src/agentic_rag/agent/model.py` | Involucro del limitatore in `build_model` |
| `src/agentic_rag/agent/agent.py` | Costanti dei motivi di rifiuto |
| `src/agentic_rag/agent/config.py`, `.env.example` | `AGENT_RPM/TPM`, `JUDGE_RPM/TPM` |
| **nuovi** in `src/agentic_rag/eval/` | `esperimento.py` (CLI, manifesto, ciclo, ripresa), `metriche.py` (metriche per esecuzione), `statistica.py` (bootstrap, appaiato, pass^k, κ: funzioni pure), `riepilogo.py`, `etichette.py` |
| `src/agentic_rag/eval/confronta.py` e il suo test | Rimossi |
| README | Sezione Valutazione: esperimenti, metriche con i nomi, comandi |
| `docs/superpowers/specs/2026-10-16-ricerca-documenti-opzione-a-design.md` | Nota: il protocollo operativo dell'ablazione ora passa dall'harness degli esperimenti (esclusioni appaiate, validità); il criterio dei 10 punti resta |

Da riusare: `valuta` e `calcola_esito` (`valutazione.py`), `MetricheFonti`/`MetricheNumeri`, `riga_pubblica`/`riga_privata` (`report.py`) come base delle righe JSONL, `carica` (`groundtruth.py`), `nome_errore`.

## Lasciato a chi implementa

Formato esatto delle righe JSONL e del riepilogo Markdown, struttura interna dei moduli, messaggi della CLI, tabella dei prezzi (vuota finché non si sceglie il modello), dettagli del watchdog del timeout.

## Ordine di implementazione (sintesi del piano che seguirà)

1. Limitatore e costanti dei rifiuti (agente).
2. Estensione di `esegui_domanda`: timeout sul tempo di lavoro, nuovi dati raccolti, classificazione degli errori.
3. `statistica.py` e `metriche.py`, con test unitari su valori noti (pass^k, κ, bootstrap con seme).
4. `esperimento.py`: manifesto, JSONL, ordine, ripresa, passaggio finale.
5. `riepilogo.py` (validità, appaiamento, verdetto) ed `etichette.py`.
6. Rimozione di `confronta`, documentazione.

## Verifica

- **Unit:**
  - funzioni statistiche su casi calcolati a mano;
  - metriche per esecuzione, compresi i casi non applicabili;
  - validità e appaiamento con JSONL sintetici;
  - manifesto che rifiuta modifiche a `src/` e al ground truth;
  - limitatore con orologio finto.
- **Integrazione** (DB reale e `FunctionModel` finto, come in `tests/test_eval_integration.py`):
  - un esperimento 2 varianti × 2 ripetizioni × 2 domande interrotto a metà (`KeyboardInterrupt` simulato) e ripreso, senza duplicati e senza esecuzioni perse;
  - un 503 simulato che lascia la combinazione aperta e viene recuperato nel passaggio finale;
  - un timeout di lavoro contato come fallimento dell'agente.
- **Prova reale breve:** 2 domande × 2 varianti × 1 ripetizione con il modello configurato, interrotta a mano e ripresa. Poi `riepilogo` per controllare a occhio tabelle e denominatori, senza aprire i file privati.
- `pytest`, `pytest -m integration`, `ruff check`.
