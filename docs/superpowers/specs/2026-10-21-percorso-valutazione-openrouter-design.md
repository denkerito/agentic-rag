# Percorso: dalla valutazione con Gemini all'esperimento finale con Claude via OpenRouter

Stato: bozza · 2026-10-21

## Perché

Servono due risultati, con un budget di circa 10 $ e senza rifare gli esperimenti più volte:
1. **Decisione:** tenere o no la ricerca semantica (criterio già fissato: almeno 10 punti di Task Success Rate in più).
2. **Benchmark per il CV:** metriche citabili, a progetto congelato e su un test set nuovo.

L'agente passa a **Claude Haiku 5.5**, il giudice a **Claude Sonnet 5.5**, entrambi tramite **OpenRouter**.

## Obiettivi, non obiettivi, anti-obiettivi

- **Obiettivi:** un solo esperimento a pagamento, preceduto da prove che costano centesimi; il costo reale di ogni indagine registrato dall'harness; nessuna esecuzione che passa per un fallimento dell'agente quando il problema è il credito o la rete.
- **Non obiettivi:** cambiare gli embedding (restano Gemini, vedi sotto); parallelizzare l'esperimento; ottimizzare il prompt per Haiku oltre il minimo indispensabile.
- **Anti-obiettivi:** ritoccare prompt, soglie o tool guardando il ground truth (`AGENTS.md`); scegliere metriche o criteri dopo aver visto i risultati; un esperimento lanciato e poi invalidato da un bug dell'harness scoperto a metà.

## Fatti verificati (2026-10-21)

| | ID su OpenRouter | Ingresso | Lettura cache | Scrittura cache (5 min) | Uscita (ragionamento incluso) |
|---|---|---|---|---|---|
| Haiku 5.5 (prompt sotto i 100K token) | `anthropic/claude-haiku-5.5` | 0,10 $ / M | 0,01 $ / M | 0,125 $ / M | 0,50 $ / M |
| Sonnet 5.5 | `anthropic/claude-sonnet-5.5` | 2 $ / M | 0,10 $ / M | 2,50 $ / M | 10 $ / M |

- OpenRouter non ricarica il prezzo dell'inferenza; trattiene il **5,5% sull'acquisto di crediti**.
- La cache per i modelli Anthropic va **attivata esplicitamente** (`cache_control`). pydantic-ai lo fa con `openrouter_cache_instructions`, `openrouter_cache_tool_definitions` e `openrouter_cache_messages`.
- OpenRouter restituisce il **costo reale** di ogni risposta. pydantic-ai lo espone in `ModelResponse.provider_details["cost"]`.
- Il ragionamento ("thinking") è fatturato come uscita. I `reasoning_details` vanno rimandati invariati tra una chiamata ai tool e l'altra, e pydantic-ai lo fa già.
- Gli endpoint Anthropic su OpenRouter non elencano `temperature` tra i parametri supportati. Il giudice oggi la imposta a 0 (`eval/giudice.py`).
- Con il client OpenAI-compatibile, gli errori di rete arrivano come `ModelAPIError`, che `ModelloGestito` oggi **non ritenta**: ritenta solo i codici HTTP temporanei, gli errori Gemini e gli errori `httpx`.
- Un **402 (credito esaurito)** o un 401/403 oggi chiude la combinazione come `fallita_agente`. Se il credito finisce a metà esperimento, tutte le combinazioni rimanenti verrebbero contate come insuccessi dell'agente.
- La versione installata di pydantic-ai è la 2.54; l'ultima è la 2.59.

## Scelte già fatte (mie, da confermare leggendo)

- **Embedding restano su Gemini** (`gemini-embedding-001`, chiave `GOOGLE_API_KEY`). Cambiarli vorrebbe dire reindicizzare e ricalibrare a mano `SEARCH_MAX_DISTANCE` (0,38). Il volume è minimo.
- **Provider fissato ad Anthropic** su OpenRouter (`order: ["anthropic"]`, `allow_fallbacks: false`). Serve per la riproducibilità e per le letture dalla cache. Se Anthropic è giù, gli errori sono di infrastruttura e li ritentano `ModelloGestito` e il passaggio finale.
- **Effort:** Haiku al suo default (`medium`), giudice Sonnet a `medium`. Il giudice è la voce più cara.
- **Cache accesa** su istruzioni, definizioni dei tool e ultimo messaggio.
- **Tentativi nel wrapper e non nel client** (`max_retries=0` sul client OpenAI), come già per Gemini: così le attese restano misurate.

## Decisioni aperte (tue)

1. **Uno o due esperimenti.**
   - **B (consigliata):** un solo esperimento sul test set nuovo, con entrambe le varianti. Nel CV va la tabella con tutte e due; nel prodotto resta la vincente. Il numero della vincente è leggermente ottimista perché viene dallo stesso esperimento che l'ha scelta; lo compensano il criterio fissato prima e il fatto di mostrare entrambe.
   - **A:** ablazione sul set attuale, poi benchmark della sola vincente sul set nuovo. È più pulita e costa circa 2-4 $ in più.
2. **Ripetizioni: 3 o 5.** Si decide dopo la prova breve, con il costo reale per indagine.
3. **Dimensione del test set nuovo.** Consiglio 20-30 domande: con 12 domande, una sola vale 8 punti, quindi il criterio dei 10 punti si gioca su poco più di una domanda.
4. **Ground truth e git.** I due file attuali sono tracciati in git, mentre il README dice che il ground truth è fuori da git. Il set nuovo lo terrei fuori (`.gitignore`), almeno fino alla fine dell'esperimento.

## Fasi

### Fase 1 — Passaggio a OpenRouter (codice, costo 0)

1. Aggiornare pydantic-ai e aggiungere il supporto OpenRouter. Aggiungere `OPENROUTER_API_KEY` in `config.py`, `.env.example` e `controlla_ambiente`; la chiave Gemini resta per gli embedding.
2. In `build_model`, il prefisso `openrouter:` costruisce il modello OpenRouter con cache, provider fissato ed effort. Il giudice ha un modello di default suo (`JUDGE_MODEL`). Si toglie `temperature=0` dal giudice.
3. In `ModelloGestito`, ritentare anche gli errori transitori del client OpenAI (`ModelAPIError` senza codice HTTP).
4. **Ritocco 1 — costo reale:** ogni esecuzione registra il costo restituito da OpenRouter (agente e giudice separati) e i token letti e scritti in cache. Il riepilogo mostra costo per indagine, totale e quota di input servita dalla cache. Non serve una tabella dei prezzi.
5. **Ritocco 2 — giudice:** a giudice acceso, un'esecuzione senza verdetto resta aperta (si ritenta nel passaggio finale) e il riepilogo conta questi casi.
6. **Ritocco 3 — errori fatali:** 401, 402 e 403 fermano l'esperimento con un messaggio chiaro e lasciano aperta la combinazione in corso. Ricaricato il credito, si riprende con la sola `--etichetta`.
7. Le impostazioni del modello che vengono da variabili d'ambiente (provider, effort, cache) entrano nel manifesto, così una ripresa con impostazioni diverse viene rifiutata.
8. Test unitari e di integrazione con modello finto, `ruff`, README.

**Si passa alla fase 2 quando:** tutti i test sono verdi e `src/` è committato.

### Fase 2 — Prova breve (circa 0,10-0,30 $)

Sul set attuale: 2 domande (una normale e una onesta) × 2 varianti × 1 ripetizione, con il giudice, interrotta a mano una volta e ripresa. Prima, gratis: lanciarla con una chiave non valida e verificare che si fermi senza chiudere combinazioni.

**Controlli sul riepilogo:**
- zero errori di infrastruttura e nessun timeout;
- ogni esecuzione ha il verdetto del giudice;
- lettura dalla cache maggiore di zero a partire dalla seconda richiesta;
- il costo registrato coincide con quello mostrato da OpenRouter nell'attività del proprio account;
- costo medio per indagine e per verdetto.

Se Haiku si comporta male, ad esempio cicli lunghi o risposte rifiutate spesso dal validatore, si ritocca il prompt provando con domande proprie e non con quelle del ground truth, e si ripete la prova.

Facoltativo: una batteria di sviluppo sul set attuale, 12 domande × 1 ripetizione (circa 0,30 $), per vedere il comportamento su tutte le modalità. Va letta come segnale di funzionamento, non come un elenco di cose da sistemare domanda per domanda.

**Si passa alla fase 4 quando:** tutti i controlli sono superati e il costo per indagine è noto.

### Fase 3 — Test set nuovo (tuo, in parallelo alle fasi 1-2)

- Stesso schema dell'attuale, stessa distribuzione di modalità (normale, onesta, non rispondibile, regolare), 20-30 domande, scritte senza guardare le risposte dell'agente.
- Cartella separata da quella attuale; l'harness la legge con `--gt`. `AGENTS.md` va aggiornato perché il divieto di accesso valga anche per la nuova cartella.
- Validazione con `python -m agentic_rag.eval --dry-run --gt <cartella>`: tutte le query attese devono girare. Con più di 25 valori numerici attesi il controllo sui numeri non si applica.

### Fase 4 — Congelamento

Commit e tag (ad esempio `eval-v1`). Da qui `src/` non cambia fino alla fine dell'esperimento: il manifesto lo impone.

### Fase 5 — Esperimento (circa 2-5 $ con 3 ripetizioni)

```bash
python -m agentic_rag.eval.esperimento esegui --etichetta finale --gt <cartella-nuova> \
    --variante con:semantica=1 --variante senza:semantica=0 --ripetizioni 3 \
    --judge --criterio "task_success_rate:con-senza>=10"
```

Prima di lanciarlo:
- impostare su OpenRouter un **limite di credito sulla chiave**, ad esempio 8 $;
- tenere il PC sveglio.

Le interruzioni si riprendono con la sola etichetta. Alla fine si controllano la validità (escluse ≤ 10% per variante) e il verdetto.

### Fase 6 — Validazione del giudice (tuo, circa un'ora, costo 0)

`etichette --campione 30`, poi compili il foglio alla cieca, poi `kappa`.

### Fase 7 — Risultati

- **README e CV:** tabella delle due varianti con intervalli al 95%, κ del giudice, costo per indagine.
- **Prodotto:** `RICERCA_SEMANTICA` si imposta secondo il verdetto.
- I report Gemini restano come storico.

## Budget

| Voce | Stima |
|---|---|
| Fasi 1, 3, 4, 6 | 0 $ |
| Fase 2 (più la batteria facoltativa) | 0,10-0,60 $ |
| Fase 5, 25 domande × 2 varianti × 3 ripetizioni (150 indagini, circa 1 centesimo l'una più 1-2 centesimi per verdetto) | 2-5 $ |
| Riserva per un rilancio | 2-5 $ |
| **Crediti da comprare** | **10 $ (più il 5,5% di commissione)** |

Le stime hanno un'incertezza di circa un fattore 2, soprattutto per la quantità di ragionamento di Haiku. La fase 2 le sostituisce con numeri misurati.

## Rischi

- **Haiku diverso da Gemini nel seguire il prompt:** emerge in fase 2, e si corregge prima del congelamento.
- **Bug dell'harness scoperto a esperimento avviato:** obbliga a una nuova etichetta. Lo mitigano la fase 2 e i tre ritocchi.
- **Provider fissato e indisponibile:** errori di infrastruttura, ritentati. Se le escluse superano il 10%, l'esperimento si dichiara non valido e si rilancia l'etichetta.
- **Potenza statistica:** anche con 25 domande il verdetto è un segnale. Va presentato con l'intervallo, come già previsto dal riepilogo.
