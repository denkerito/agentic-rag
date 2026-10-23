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

- **Embedding restano su Gemini**, passati a `gemini-embedding-2` (chiave `GOOGLE_API_KEY`): documenti reindicizzati e `SEARCH_MAX_DISTANCE` ricalibrata a mano a 0,30 con query non del test set (pertinenti 0,20-0,24, aziendali assenti ≥ 0,32, fuori tema ≥ 0,43).
- **Provider fissato ad Anthropic** su OpenRouter (`order: ["anthropic"]`, `allow_fallbacks: false`). Serve per la riproducibilità e per le letture dalla cache. Se Anthropic è giù, gli errori sono di infrastruttura e li ritentano `ModelloGestito` e il passaggio finale.
- **Effort:** Haiku al suo default (`medium`), giudice Sonnet a `medium`. Il giudice è la voce più cara.
- **Cache accesa** su istruzioni, definizioni dei tool e ultimo messaggio.
- **Tentativi nel wrapper e non nel client** (`max_retries=0` sul client OpenAI), come già per Gemini: così le attese restano misurate.

## Decisioni aperte (tue)

1. **Uno o due esperimenti.** *Decisa il 2026-10-22: B.* Le 12 domande attuali sono diventate il set di sviluppo (vedi «Revisione del ground truth di sviluppo»), quindi l'esperimento finale si fa solo sul test set nuovo.
   - **B (consigliata):** un solo esperimento sul test set nuovo, con entrambe le varianti. Nel CV va la tabella con tutte e due; nel prodotto resta la vincente. Il numero della vincente è leggermente ottimista perché viene dallo stesso esperimento che l'ha scelta; lo compensano il criterio fissato prima e il fatto di mostrare entrambe.
   - **A:** ablazione sul set attuale, poi benchmark della sola vincente sul set nuovo. È più pulita e costa circa 2-4 $ in più.
2. **Ripetizioni: 3 o 5.** Il costo reale ora è noto: circa 0,01 $ per indagine col giudice (vedi «Esito della fase 2»). Con 12 domande e una ripetizione, 5 domande su 12 hanno cambiato esito tra le due varianti: le ripetizioni servono.
3. **Dimensione del test set nuovo.** Il costo non è più il vincolo; lo è il tempo per scrivere il ground truth.
   - **25 domande** (circa 1,5 $ con 3 ripetizioni): bastano per la decisione di prodotto. Con 12 domande una sola vale 8 punti, con 25 ne vale 4.
   - **50-60 domande** (circa 3 $): necessarie se si vuole affermare che i vettori «non servono» (vedi il punto 5).
4. **Ground truth e git.** I due file attuali sono tracciati in git, mentre il README dice che il ground truth è fuori da git. Il set nuovo lo terrei fuori (`.gitignore`), almeno fino alla fine dell'esperimento.
5. **Non-inferiorità come analisi secondaria.** Il criterio decide sulla stima puntuale (`con − senza ≥ 10`): se non è superato, la frase corretta è «la ricerca semantica non ha dato il miglioramento richiesto», non «non serve». Per sostenere la seconda serve il limite superiore dell'IC 95% di `con − senza` sotto i 10 punti. Con 25 domande l'intervallo sarà largo circa ±20 punti; servono nell'ordine di 60-100 domande (stima grezza). Va aggiunta, se la si vuole, prima di vedere i dati.
6. **Metrica principale.** Proposta: resta il Task Success Rate, come fissato il 2026-10-19 (dopo la correzione della misura dei numeri, vedi sotto). Answer Accuracy e quota di risposte `errata` si riportano come secondarie. Cambiare la metrica principale adesso sarebbe una scelta fatta dopo aver visto le batterie.

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

## Esito della fase 2 (2026-10-22)

Solo dati dei report pubblici (`eval/reports/esperimenti/`): nessun valore del ground truth.

### Prova breve e costo misurato

`prova` (2 domande × 2 varianti, con il giudice): 0,053 $ in tutto, nessun errore di infrastruttura, ogni esecuzione con il verdetto, cache all'84-85% dell'input. Nelle batterie: circa **0,004 $ per indagine dell'agente e 0,005 $ per verdetto**.

### Batteria di sviluppo come controllo di funzionamento

Soglie fissate **prima** di lanciarla (per la variante `senza`):
- zero errori di infrastruttura e timeout, ogni esecuzione con il verdetto del giudice;
- nessuna causa inventata (False Acceptance Rate 0);
- al massimo 2 risposte `errata` su 12;
- almeno 5 `ok` su 12 (la vecchia batteria Gemini, solo vettori e senza giudice, aveva fatto 5/12).

| | `senza` (`batteria-senza`) | `con` (`batteria-con`) |
|---|---|---|
| Task Success Rate | 3/12 | 4/12 |
| Giudice: corrette / parziali / errate | 9 / 3 / 0 | 7 / 5 / 0 |
| Cause inventate | 0/2 | 0/2 |
| Errori di infrastruttura, senza verdetto | 0, 0 | 0, 0 |
| Richieste medie | 6,6 | 5,7 |

`senza` non supera la soglia degli `ok`; le altre tre sì. Regola fissata prima di lanciare `con`: se anche `con` fa al massimo 4/12, l'incompletezza dipende dal modello o dalla misura e non dalla v2. È andata così. Le domande `ok` delle due varianti coincidono su una sola: 5 domande su 12 hanno cambiato esito, quindi gran parte della differenza tra due esecuzioni singole è rumore.

### Sonde su domande nostre

Cinque domande scritte sul database, su parti dei dati senza anomalie e quindi lontane dalle storie del test, con la risposta di riferimento calcolata in SQL. Due esecuzioni ciascuna sulla variante `senza`.
- **ID citati completi in 10 esecuzioni su 10.** Le domande semplici si chiudono in 2-3 richieste: poche richieste non vogliono dire una risposta incompleta.
- I numeri «mancanti» venivano da due cause:
  1. **misura:** l'harness contava solo la conclusione e `numeri[].valore`, mentre l'agente scrive spesso i valori dei due periodi in `numeri[].descrizione` («aprile 1.100 → maggio 450») e la differenza nel valore;
  2. **vista senza fonti:** `v_margine_mensile` non aveva una colonna `fonti`, il validatore rifiuta i numeri senza fonti, e l'agente spostava i totali di ricavi, costi e margine nei `limiti`, dove non contano.
- Gli ID mancanti nelle batterie **non si riproducono** sulle domande nostre e restano senza spiegazione. Le cause documentate del dataset sono le storie del test, quindi non si possono scrivere sonde su di esse senza sovrapporsi al ground truth.

### Correzioni (trovate con le sonde, non guardando il ground truth)

- **A, misura dei numeri** (`eval/numeri.py`): contano anche i numeri di `numeri[].descrizione`. Quelli nei `limiti` no: lì va ciò che non è verificato, e contarli premierebbe i numeri senza fonti.
- **B, fonti nel margine** (`db/schema_views.sql`): `v_margine_mensile` espone `fonti`; le viste si aggiornano con `init --views-only`.
- **Client chiuso a ogni domanda e a ogni verdetto** (`agent/model.py`, `eval/runner.py`, `eval/giudice.py`): l'`AsyncOpenAI` di OpenRouter non veniva chiuso. Con un `asyncio.run` per domanda, il garbage collector lo chiudeva nel ciclo della domanda successiva e il log mostrava `RuntimeError: Event loop is closed`. Nessun effetto sui risultati, ma i traceback avrebbero potuto nascondere errori veri nel log dell'esperimento. La prima correzione chiudeva solo il client dell'agente e la sua verifica girava senza giudice; `batteria2-*` ha mostrato che restava quello del giudice. Il giudice usava `run_sync`, che lascia il client legato a un ciclo di eventi orfano. Ora agente e giudice usano lo stesso `poi_chiudi`, e la riproduzione con il giudice acceso passa da 2 traceback a 0.

Rilanciando le sonde dopo A e B, tutte le risposte risultano complete. L'unica eccezione dipende da un errore nella risposta di riferimento: era indicato l'imponibile, mentre l'agente riporta il totale IVA inclusa. Il prompt non è stato modificato.

**Conseguenze:** le batterie di oggi sono state misurate prima di A e B e non sono confrontabili con le esecuzioni successive. Prima del congelamento si rilancia il controllo di funzionamento su entrambe le varianti, con le stesse soglie.

### Controllo di funzionamento dopo A e B (`batteria2-*`)

| | `senza` (`batteria2-senza`) | `con` (`batteria2-con`) |
|---|---|---|
| Task Success Rate | 2/12 | 4/12 |
| Giudice: corrette / parziali / errate | 10 / 2 / 0 | 8 / 3 / 0 (11 completate) |
| Cause inventate | 0/2 | 0/2 |
| Errori di infrastruttura, senza verdetto | 0, 0 | 0, 0 (1 fallita per l'agente: `UnexpectedModelBehavior`) |

Il controllo **non è superato di nuovo**: `senza` fa 2/12 `ok` contro i 5 richiesti, mentre le altre soglie sono rispettate. A e B non hanno cambiato il Task Success Rate sulle domande del test. In quattro batterie, su 47 risposte completate: nessuna `errata`, nessuna causa inventata, ID citati al 70-76% e numeri trovati al 70-73%.

Sulle sonde l'agente è completo, quindi ciò che manca è qualcosa che il ground truth si aspetta. Per capirlo si sono letti i report privati: le 12 domande sono diventate il **set di sviluppo** (`AGENTS.md`) e non servono più a misurare.

## Revisione del ground truth di sviluppo (2026-10-22)

Lettura dei report privati delle quattro batterie e verifica di ogni ID e numero sul DB e sui CSV. Dei 10 `ko` di `batteria2-senza`, circa due e mezzo sono mancanze dell'agente (Q4, Q9 e metà di Q1). Gli altri dipendono da errori o richieste eccessive del ground truth e dell'harness. Il giudice non ha mai dato `errata`.

### Errori di fatto corretti

| | Era | Corretto (verificato sui dati) |
|---|---|---|
| Q6 / ST-03 | Barilli 291.500 €, 27,51% | 284.000 € su 1.059.400 €, **26,81%** (lo diceva anche la query attesa). Il giudice penalizzava la risposta giusta |
| Q7 / ST-04 | media trasferte circa 2.100 €, +210%; fatture `FATT-P-2025-0182`…`0193` | media **1.850 €** (ogni altro mese), +4.650 €, +251%; fatture di novembre `0197`…`0208` (le altre sono di giugno-settembre) |
| Q10 | trasferte aggregate come «categoria» più cresciuta | allineata alla query attesa, per conto: 64.01 +2.250 € in valore assoluto, 64.03 +266,7% in percentuale, poi 61.02 +1.360 €. La lettura aggregata resta accettata |
| Q3 | media altri mesi circa 79.000 € | 80.268,64 € |
| Q12 | `SCD-0015` (è l'adeguamento ISTAT dell'affitto) | `SCD-0019`, promemoria del preavviso Altocumulo (15/08/2026) |
| ST-01 | `SCD-0009` (è un F24) | `SCD-0013`, termine di preavviso del contratto Nimbus |
| ST-02 | `MOV-000084` (è un incasso da un cliente) | `MOV-000069`, pagamento della fattura legale (07/04/2025) |

**Bug dell'harness:** i codici conto (`64.01`) dei CSV venivano letti come numeri e le query attese che li confrontano come testo restituivano 0 righe. La query di Q7 era vuota.

### Richieste che la domanda non fa, tolte

- **Numeri** (la query attesa restituiva celle che nessuna risposta riporta):
  - Q1: margine in euro invece che in percentuale;
  - Q2 e Q8: solo imponibili, senza IVA e totali;
  - Q5: solo le due fatture Barilli prima e dopo il cambio, invece del fatturato di ogni cliente in ogni mese (19 valori);
  - Q9: il totale della fattura, non la somma dei due pagamenti.
- **Tabelle** che imponevano un percorso:
  - Q10 `fatture_righe`: le scritture contabili sono una fonte equivalente;
  - Q12 `scadenzario`: la scadenza è nel contratto.
- **Q11:** il controllo delle domande non rispondibili ammette numeri di contesto. Restano causa non documentata, limiti e confidenza non alta.

### Cosa resta richiesto, e perché

Le fonti di supporto che l'agente non cerca restano nel ground truth: CTR-001 e DOC-EML-001 in Q1, DOC-PRV-001 in Q3 e Q4, DOC-EML-005 in Q4, DOC-EML-012 in Q9. L'agente trova il primo documento che spiega la causa e si ferma. Per il commercialista contratto, comunicazione e conferme sono verificabilità in più, quindi è una mancanza dell'agente, non del ground truth. Criterio della revisione: si corregge il ground truth dove è sbagliato o chiede ciò che la domanda non chiede, mai per far passare l'agente.

### Linee guida per il test set nuovo

1. La query attesa restituisce **solo i numeri che la risposta deve contenere**: niente colonne di contorno (IVA, totali, ID numerici) ed elenchi solo se la domanda li chiede.
2. Le tabelle attese (`*.csv` in `fonti_attese`) si indicano solo quando il percorso è obbligato.
3. Ogni ID e ogni numero della risposta attesa si controlla sul DB prima di congelare il set.
4. Risposta attesa e query attesa devono dire la stessa cosa (stessa granularità, stesse definizioni).
5. Nelle query i codici si confrontano come testo (`categoria = '64.01'`).
6. Validazione con `python -m agentic_rag.eval --dry-run --gt <cartella>`: tutte le query `ok` e il numero di valori attesi previsto.

## Anteprima invece di risultati SQL tagliati (2026-10-22)

`batteria3-senza`, Q9: l'unica `errata` dopo la revisione. La query delle coppie di fatture restituiva 873 righe, `query_sql` ne mostrava le prime 50 con `troncato: true`, e la coppia duplicata era alla riga 841. L'agente ha concluso «nessuna fattura pagata due volte». Un risultato tagliato sembra comunque un risultato.

**Regola:** un risultato è intero oppure è dichiaratamente un'anteprima.
- **Intero** se il JSON restituito sta in `SQL_MAX_CARATTERI = 30.000`. La taratura è fatta sulle 302 SQL dell'agente nelle batterie del 22/10: mediana 1.014 caratteri, p99 25.643, solo 2 oltre i 30.000. Le analisi annuali per conto (213 righe) prima venivano tagliate a 50 righe e ora arrivano intere.
- **Anteprima** oltre la soglia:
  - `totale_righe` (esatto fino a 5.000 righe lette);
  - 5 righe d'esempio;
  - il profilo di tutte le colonne: distinti e nulli; min, max e somma per i numeri; intervallo delle date; valori elencati se sono al massimo 10; lunghezze degli array;
  - le colonne adatte a un `GROUP BY`;
  - una nota che chiede di aggregare o filtrare prima di concludere.
- Citabili solo gli ID visti, cioè anteprima e profilo. Un risultato al limite costa circa 10.000 token (circa 0,0015 $ con la cache); un'anteprima costa meno delle vecchie 50 righe.

Un budget in caratteri da solo era stato scartato: sposta il punto di taglio, ma una riga utile in fondo resta invisibile.

## Prova dell'assenza, principi e confidenza (2026-10-23)

Restavano tre comportamenti dell'agente: falsi «non c'è» (Q9), cause secondarie e documenti di supporto non cercati (Q1, Q3, Q4, Q5) e confidenza «alta» sulle domande non rispondibili (Q11).

**Regole introdotte**, uguali per `con` e `senza`:
- **ID delle query e prova dell'assenza.** Ogni `query_sql` ha un ID (`Q1`, `Q2`…). Un'affermazione «nei dati non esiste / non è accaduto» si dichiara in `assenze`, insieme alla query che la prova. Il validatore accetta l'assenza solo se la query esiste, il risultato era completo (non un'anteprima) ed era vuoto oppure con soli conteggi a zero; altrimenti scatta il rifiuto `assenza_non_provata`. Un elenco di candidati non prova un'assenza.
- **Principio 3 (due canali):** un'assenza nei dati si verifica sia nei dati sia nei documenti.
- **Principio 4 (documenti di supporto):** la spiegazione va cercata per ogni voce che spiega la variazione, non solo per la principale, insieme ai documenti collegati (contratto, comunicazione formale, conferme). Il prompt continua a non nominare i tool di ricerca.
- **Confidenza:** alta = verificato con le fonti; media = verifica parziale; bassa = dati insufficienti o domanda non rispondibile.
- **UI:** le assenze verificate compaiono con il rimando alla query, e ogni passo SQL mostra il suo ID.

**Limite dichiarato:** il validatore controlla completezza e risultato, non i criteri della query. Se l'agente cerca con criteri sbagliati e trova zero righe, l'assenza passa il controllo. Coprono quel caso la conferma nei documenti e la query visibile al commercialista.

### Verifica

- **Replay della Q9** (conversazione con l'anteprima da 873 righe, `senza`, 3 volte): duplicato trovato 3 volte su 3 (prima 2 su 3). In ogni replay il validatore rifiuta una prima assenza non provata, e l'agente la corregge.
- **Batteria sul set di sviluppo, 2 ripetizioni per variante:**

| | `senza` b3 → b4 | `con` b3 → b4 |
|---|---|---|
| Task Success Rate | 6/12 → **16/24 (67%)** | 6/12 → **16/24 (67%)** |
| Risposte `errata` | 1 → **0** | 0 → **0** |
| Cause inventate | 0 → 0 | 0 → 0 |
| ID citati / numeri trovati | 77% / 78% → 89% / 90% | 84% / 95% → 92% / 98% |
| Indagini fallite per l'agente | 0 → 1 | 0 → 1 |
| Costo dell'agente per indagine | 0,0039 $ → 0,0055 $ | 0,0040 $ → 0,0064 $ |

- **Migliorate:**
  - Q9: duplicato trovato 4 volte su 4, nessuna `errata`;
  - Q11: `ok` 4 volte su 4, confidenza bassa;
  - Q1 `con`: la causa secondaria Nimbus è attribuita e documentata, giudice `corretta` (prima `parziale`);
  - Q5: CTR-008 citato.
- **Restano:**
  - documenti di supporto non citati: CTR-001 (Q1), DOC-EML-005 (Q4), DOC-EML-012 (Q9);
  - Q3, prima ripetizione, in entrambe le varianti: fallita dopo tre risposte rifiutate per fonti mai viste o numeri senza fonti, un guasto già visto in `batteria2-con` e indipendente dal nuovo validatore;
  - circa un rifiuto `assenza_non_provata` ogni due indagini, tutte poi chiuse.
- **Costo:** +40-60% per indagine (più ricerche e più rifiuti), comunque basso. L'esperimento finale con 25 domande, 2 varianti e 3 ripetizioni costerebbe circa 1,8 $ col giudice.

**Regola di stop:** da qui l'agente non si ritocca più sul set di sviluppo. I `ko` rimasti si inseguirebbero solo spingendo l'agente verso documenti specifici di queste 12 domande. Il numero che conta verrà dal test set nuovo.

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
