# Ricerca nei documenti: navigazione per metadati + full-text + semantica (opzione A)

Stato: approvato · 2026-10-16

## Perché

Oggi l'agente trova i documenti con un solo canale: la ricerca vettoriale (`cerca_documenti`) con una soglia di
distanza coseno fissa (0.38, calibrata a mano). Due conseguenze:

- **Un risultato negativo non è dimostrabile.** «Nessun chunk sotto soglia» è un'affermazione sulla soglia, non
  sui documenti. Proprio il caso in cui il progetto promette onestà («la causa non è documentata») poggia sul canale
  meno verificabile.
- **Debolezza su termini esatti** (nomi, codici, importi) e nessun modo per l'agente di dire «ho guardato tutti i
  documenti di questo fornitore in questo periodo».

L'opzione A dà all'agente strumenti di ricerca semplici e deterministici, e lascia a lui la strategia, coerentemente
con la tesi del progetto («l'agente decide il percorso in base a ciò che scopre»). La ricerca semantica resta come
canale per le parafrasi; un esperimento successivo decide se tenerla.

## Obiettivi

1. L'agente può **elencare i documenti per metadati** (tipo, periodo, cliente, fornitore) senza soglie.
2. L'agente può **cercare parole nel testo** (full-text italiano, con stemming), con un risultato binario:
   un documento contiene i termini oppure no.
3. La **ricerca semantica** resta disponibile come tool separato e **si può spegnere da configurazione**, senza
   cambiare prompt né altri tool, per l'ablazione.
4. L'architettura è **credibile con migliaia di documenti**: indici veri, risultati paginati o limitati, mai testi
   completi in massa nel contesto.
5. Ogni ricerca è un **passo distinto e leggibile** nella UI e nello storico.
6. Un **esperimento con criterio fissato in anticipo** decide se i vettori restano.

## Non obiettivi

- Ricerca ibrida con fusione (RRF) o re-ranker: valutata e scartata per questa iterazione (vedi «Alternative»).
- Estrazione strutturata dei documenti con LLM in ingestione: esclusa (introdurrebbe dati generati da LLM nel DB).
- Indice dei documenti nel prompt: non scala.
- Modifiche a `query_sql`, alle viste, al validatore delle fonti, al runner, all'autenticazione.
- Vincolo nel validatore «`causa_documentata=false` richiede almeno una ricerca testuale»: possibile passo
  successivo, non in questa iterazione.

## Anti-obiettivi (fallimento anche se funziona)

- Ritoccare prompt, docstring o soglie **dopo** aver visto i risultati dell'eval per far passare le domande
  (vietato da `AGENTS.md`).
- Una variante «senza vettori» penalizzata da dettagli dell'harness invece che dalla qualità delle risposte.
- Il prompt che nomina i tool di ricerca: renderebbe l'ablazione un cambio di due variabili.

## Vincoli

- Modello di default invariato (`AGENT_MODEL`, oggi `google:gemini-3.5-flash-lite`); il design funziona con
  qualsiasi modello configurato.
- Tutto in PostgreSQL 17 + pgvector già presenti; nessuna nuova infrastruttura.
- Il ruolo `agent_ro` resta l'unico con cui l'agente legge i dati.
- Il ground truth in `eval/ground_truth/` non viene aperto da chi sviluppa (vedi `AGENTS.md`).

## Design

### Tool dell'agente

| Tool | Stato | Ruolo |
|---|---|---|
| `query_sql` | invariato | numeri |
| `elenca_documenti` | **nuovo** | indice dei documenti per metadati, paginato |
| `cerca_testo` | **nuovo** | full-text italiano su titolo e contenuto |
| `cerca_semantica` | **rinominato** da `cerca_documenti`, logica invariata | parafrasi; disattivabile |
| `apri_documento` | invariato | lettura del documento |

**`elenca_documenti(tipo?, data_da?, data_a?, cliente_id?, fornitore_id?, pagina=1)`**
- Restituisce `totale`, `pagina`, `pagine` e, per ogni documento: `doc_id`, `tipo`, `data`, `titolo`,
  `cliente_id`/`fornitore_id` con la denominazione della controparte. Nessun testo.
- 30 documenti per pagina, ordinati per data (poi `doc_id`).
- **Non** aggiunge gli ID a `seen_ids`: un documento visto solo per titolo non è citabile. Diventa citabile quando
  viene aperto o compare in una ricerca con il suo testo.

**`cerca_testo(query, tipo?, data_da?, data_a?, cliente_id?, fornitore_id?, k=5)`**
- `websearch_to_tsquery('italian', query)`: il modello può usare `or`, frasi tra virgolette e `-escludi`. La
  docstring insegna a usare `or` tra sinonimi (di default le parole sono in AND).
- Corrispondenza su una colonna `tsvector` di `documenti`: titolo con peso A, contenuto con peso B (generata,
  indice GIN). Il livello è il **documento**, non il chunk: non serve allinearsi ai vettori (in A i canali sono
  separati) e la ricerca testuale non dipende dalla pipeline di embedding, che nella variante senza vettori non serve.
- Restituisce `totale` (numero di documenti con corrispondenza) e i primi `k` (max 8) ordinati per `ts_rank_cd`,
  ciascuno con `doc_id`, `titolo`, `tipo`, `data` e 1–2 frammenti evidenziati (`ts_headline`).
- **Pertinente = contiene i termini**: nessuna soglia.
- Zero risultati → nota esplicita: provare sinonimi o togliere filtri prima di concludere che non è documentato.
- Query che dopo l'analisi non contiene termini utili (solo stopword) → `ModelRetry` con messaggio chiaro.
- I `doc_id` restituiti entrano in `seen_ids` (come oggi per la ricerca semantica).

**`cerca_semantica`**: il `cerca_documenti` di oggi, con il nuovo nome e la docstring che ne chiarisce il ruolo
(concetti e parafrasi, non nomi o codici). Inoltre, per la credibilità con filtri a scala, abilitare la scansione
iterativa HNSW di pgvector (`hnsw.iterative_scan`) se la versione installata la supporta (≥ 0.8).

### Accesso ai documenti solo tramite tool (scelta mia)

`documenti` viene esclusa dalle relazioni interrogabili da `query_sql` e dal DDL nel prompt, come già
`documenti_chunks`. Motivi: ogni accesso ai documenti passa da un tool tracciato e mostrato nella UI; a scala,
`SELECT contenuto ...` riempirebbe il contesto; nessun canale lessicale «di riserva» via `ILIKE` falsa l'ablazione.

### Configurazione e ablazione

- Nuova variabile `RICERCA_SEMANTICA` (default attiva). Spenta, `cerca_semantica` non viene registrato tra i tool.
- `open_session` accetta il parametro corrispondente, così API, CLI ed eval usano lo stesso percorso.
- Il **prompt di sistema non nomina i tool di ricerca nei documenti**: le indicazioni specifiche stanno nelle
  docstring. Il prompt mantiene un principio indipendente dai tool, per esempio: «prima di dichiarare una causa non
  documentata, cerca con più formulazioni e sinonimi e usa i filtri di periodo e controparte». Il principio 3, che
  oggi cita `cerca_documenti`, va riformulato.

### API, eventi, UI

- `events.py`: traduzione dei risultati dei nuovi tool in `tool_result` (ID e conteggi, mai il testo). Serve un
  campo `totale` in `ToolResult` per `elenca_documenti` e `cerca_testo`.
- Frontend (`Passi.tsx`): titolo, icona, riepilogo e argomenti per i tre tool di ricerca. Esempi di riepilogo:
  «12 documenti (pagina 1 di 1)», «3 documenti con corrispondenza su 3», «Nessuna corrispondenza».
- **Storico**: le indagini già salvate contengono eventi `cerca_documenti`; la UI continua a mostrarli
  (etichetta legacy). Lo stesso vale per la mappa `TABELLE_PER_TOOL` dell'eval.

### Dati e migrazione

- Colonna generata e indice GIN in `schema.sql`.
- Per un database già inizializzato serve un modo di applicarli senza `--reset` (che cancella anche gli embedding),
  sullo stile di `--comments-only`; in alternativa documentare `--reset` + reindicizzazione (economica: 62 documenti).
  Scelta lasciata a chi implementa.

### Eval

- Nuova opzione dell'harness per spegnere la ricerca semantica; il valore finisce nel `meta` dei report.
- `TABELLE_PER_TOOL`: `elenca_documenti` e `cerca_testo` → `documenti`; `cerca_semantica` → `documenti`,
  `documenti_chunks`; chiave legacy `cerca_documenti` mantenuta.
- Script di confronto sui **report pubblici** JSON: raggruppa per (modello, ricerca semantica) e riporta per
  domanda e in totale il numero di esiti `ok`, le richieste medie e la durata media.

### Protocollo dell'esperimento (fissato prima di eseguirlo)

- Due varianti: **A completa** (con `cerca_semantica`) e **A senza semantica**. Stesso modello, stesso prompt,
  stessa versione del codice.
- Modello: `google:gemini-3.5-flash-lite` per tutte le esecuzioni (modelli più grandi solo per prove isolate,
  fuori dall'esperimento).
- Giudice LLM acceso (`--judge`), con lo stesso modello flash-lite: con il giudice, `ok` richiede anche un verdetto
  diverso da `errata`.
- 5 esecuzioni complete dell'harness per variante.
- Criterio: **i vettori restano solo se la variante completa ottiene almeno 10 punti percentuali in più di esiti
  `ok`** sul totale delle 60 esecuzioni (12 domande × 5). Altrimenti vince la variante più semplice e la ricerca
  semantica viene rimossa (tool, indice, indicizzatore) in un cambiamento successivo.
- Nessuna modifica a prompt, docstring o limiti tra le esecuzioni né dopo, in funzione dei risultati.
- Limiti invariati: 25 richieste per domanda, timeout di 300 s per domanda. *(scelta mia)*
- Esiti `errore` *(scelta mia)*: `UsageLimitExceeded` conta come non `ok` (è un fallimento della strategia di
  ricerca, non dell'infrastruttura). Errori del provider (HTTP 429/5xx) e timeout vengono rieseguiti una volta; se
  falliscono ancora contano come non `ok` e sono riportati a parte dallo script di confronto.
- L'esecuzione dell'esperimento fa parte del lavoro (ultima fase), così come l'aggiornamento del README con i
  risultati. Se durante l'esperimento emerge un bug che tocca il comportamento dell'agente, lo si corregge e si
  rieseguono **tutte** le esecuzioni di entrambe le varianti. *(scelta mia)*
- Limite dichiarato: 12 domande e 62 documenti misurano la qualità, non la tenuta a scala. La scala si argomenta
  con il design (indici, paginazione, limiti).

### Test

- Unit: traduzione degli eventi dei nuovi tool; registrazione condizionale di `cerca_semantica`; il prompt non
  nomina i tool di ricerca nei documenti.
- Integrazione (DB): stemming italiano (forma flessa che trova la base), filtri, `totale`, nota sui risultati vuoti,
  retry sulla query vuota; `elenca_documenti` con paginazione e senza effetti su `seen_ids`; `documenti` non
  interrogabile da `query_sql`.

### Documentazione

README: architettura, elenco dei tool, «Scelte di progetto» (perché A e non l'ibrida), sezione «Quando le prove non
ci sono» aggiornata; risultati dell'esperimento quando disponibili.

## Alternative considerate

- **Ricerca ibrida in un solo tool (RRF)**: più robusta con modelli piccoli e ablazione più pulita, ma incorpora
  la strategia nello strumento (contro la tesi «decide l'agente») e richiede una regola di pertinenza composta.
  Sarebbe la scelta con un modello piccolo fisso.
- **Solo metadati + indice nel prompt**: non copre i documenti senza controparte (14 su 62) e non scala.
- **Vettori migliorati (re-ranker, soglie per tipo)**: non rende verificabile un risultato negativo.

## Lasciato a chi implementa

Normalizzazione del ranking (`ts_rank_cd`), opzioni di `ts_headline`, icone e testi della UI, meccanismo di
migrazione, forma dello script di confronto, dettagli dei test.
