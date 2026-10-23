# Guida: dal test set nuovo ai risultati finali

Percorso completo deciso il 2026-10-23. Le 12 domande in `eval/ground_truth/` sono il set di sviluppo: ci abbiamo tarato agente, validatore e ground truth, quindi non misurano più nulla. Il numero da citare nel README e nel CV verrà **solo** dal test set nuovo, scritto da te e mai visto dall'assistente.

Legenda: **[tu]** = lo fai tu · **[Claude]** = lo chiedi a Claude in sessione · **[insieme]** = decisione o controllo condiviso.

---

## Fase 0 · Protezione (prima di creare la cartella)

- [ ] **[Claude]** Aggiungere in `AGENTS.md` la regola: «La cartella `eval/ground_truth_finale/` e i report privati dei suoi esperimenti sono vietati all'assistente fino alla fine dell'esperimento finale. L'assistente ne conosce solo la struttura; il codice dell'harness li legge a runtime senza stamparne il contenuto.»
- [ ] **[Claude]** Aggiungere `eval/ground_truth_finale/` al `.gitignore` (decisione 4 della spec: il set nuovo resta fuori da git fino alla fine dell'esperimento).
- [ ] **[tu]** Da qui in poi non incollare mai in chat domande, risposte attese o pezzi dei report privati del set finale.

## Fase 1 · Tre decisioni, prima di scrivere una domanda

Vanno prese e scritte nella spec **prima** di vedere qualunque risultato.

| Decisione | Opzioni | Cosa comporta |
|---|---|---|
| **Dimensione** | 25 domande · 50-60 domande | 25: basta per la decisione di prodotto; intervallo sulla differenza tra le varianti di circa ±20 punti. 50-60: ti permette di provare la non-inferiorità («i vettori non servono»); circa il doppio del tempo di scrittura |
| **Metrica principale** | Task Success Rate (consigliata) · Answer Accuracy accanto | Il TSR è il criterio fissato il 19/10; Answer Accuracy e quota di `errata` si riportano comunque come secondarie |
| **Non-inferiorità** | sì · no | Sì: oltre al criterio dei +10 punti si riporta il limite superiore dell'IC 95% di (con − senza); è significativa solo con 50+ domande |

- [x] **[tu]** Scelte il 2026-10-23:
  - **50-60 domande**;
  - **entrambe le metriche riportate con lo stesso peso**: il criterio di decisione resta sul Task Success Rate (+10 punti, fissato il 19/10), e l'Answer Accuracy viene presentata accanto, non come secondaria;
  - **non-inferiorità: sì**.
- [ ] **[Claude]** Le scrive nella spec, sezione «Decisioni aperte», con data.

## Fase 2 · Scrivere il test set

### 2.1 Cartella e formato

Crea `eval/ground_truth_finale/` con due file, nello **stesso formato** del set di sviluppo:

`domande_test.yaml` (esempio con valori inventati):

```yaml
domande:
  - id: 1
    domanda: "Perché i costi di X sono saliti a maggio?"
    storia_id: "ST-01"            # opzionale: raggruppa le domande per storia
    tipo: "multi-passo"           # la modalità si ricava da qui, vedi sotto
    risposta_attesa: >
      Testo della risposta corretta, con cause e numeri essenziali.
    fonti_attese:
      - "DOC-EML-999"             # ID che una risposta completa deve citare
      - "FATT-P-2025-9999"
      - "fatture.csv"             # tabella: solo se il percorso è obbligato
    query_sql: >
      SELECT ...                  # gira su SQLite costruito dai CSV di data/csv
```

`storie.yaml` (opzionale): `storie: [{id: "ST-01", titolo: "..."}]`.

**Modalità**, ricavata dal campo `tipo`:
- contiene «non rispondibile» → `non_rispondibile`: l'agente deve dire che non si può rispondere, con confidenza non alta;
- contiene «non documentata» → `onesta`: deve dichiarare la causa non documentata, senza inventarla;
- contiene «regolare» → `regolare`: nessuna anomalia, l'esito è «è regolare»;
- altrimenti → `normale`.

### 2.2 Distribuzione consigliata

Simile al set di sviluppo, con in più le domande «negative»:

| Modalità | su 25 | su 50 |
|---|---|---|
| normale (cause documentate, numeri, confronti) | 15 | 30 |
| normale con **risposta corretta «no»** (es. «ci sono fatture non pagate?» quando non ce ne sono), verificabile con una query | 3 | 6 |
| onesta (causa non documentata) | 3 | 6 |
| non rispondibile | 2 | 4 |
| regolare | 2 | 4 |

Varia i tipi: cause con un solo documento, cause con più documenti, numeri senza causa, controlli contabili, scadenze e contratti, confronti tra periodi diversi da quelli del set di sviluppo.

### 2.3 Regole per ogni domanda (dalla revisione del set di sviluppo)

- [ ] **La query attesa restituisce solo i numeri che la risposta deve contenere.** Niente colonne di contorno (IVA, totali, ID numerici, conteggi non chiesti). Niente elenchi, salvo che la domanda li chieda. Oltre 25 valori il controllo sui numeri non si applica.
- [ ] **Risposta attesa e query attesa dicono la stessa cosa:** stessa granularità, stesse definizioni. Esempio da evitare: query per singolo conto e risposta per categoria aggregata.
- [ ] **Fonti attese = quelle necessarie.** Il documento che prova la causa e le fatture o i movimenti decisivi. Una risposta che li cita tutti è «completa»: non aggiungere documenti di contorno se non sono davvero richiesti.
- [ ] **Tabelle (`*.csv`) solo se il percorso è obbligato.** Se la risposta si può trovare per due strade, non indicarne una.
- [ ] **Ogni ID e ogni numero si controllano sul database** prima di congelare. Nel set di sviluppo c'erano 8 errori di fatto.
- [ ] **Nelle query i codici si confrontano come testo** (`categoria = '64.01'`), e le colonne sono quelle dei CSV (`data/csv/*.csv`, con `strftime` di SQLite per le date).
- [ ] **Scrivi la domanda senza guardare le risposte dell'agente** e senza provarla sull'agente.

### 2.4 Verifiche prima di consegnare

- [ ] **[tu]** `python -m agentic_rag.eval --dry-run --gt eval/ground_truth_finale`: tutte le query `ok`, numero di valori attesi plausibile, 0 fonti non riconosciute.
- [ ] **[tu]** Per ogni domanda, apri gli ID citati (UI o DB) e rileggi la risposta attesa contro i dati.
- [ ] **[Claude]** Validazione **strutturale** senza leggere i file: si può chiedere un comando che stampi solo conteggi (modalità, numero di domande, ID esistenti nel DB sì/no). Il comando lo lanci tu, e mostri a Claude solo i conteggi.

## Fase 3 · Preparazione dell'esperimento

- [ ] **[tu]** Attiva la **fatturazione su Gemini** (Google AI Studio → piano a pagamento) e un limite di spesa.
- [ ] **[tu]** Su OpenRouter imposta un **limite di credito sulla chiave** (per esempio 8 $) e controlla il saldo.
- [ ] **[Claude]** **Congelamento:** `main` pulito, tutti i test verdi, tag `eval-v1`. Da qui `src/` non cambia (il manifesto lo impone).
- [ ] **[tu]** PC sveglio e collegato per tutta la durata: 1-2 ore con 25 domande, 2-4 ore con 50.

## Fase 4 · Esperimento

- [ ] **[tu o Claude]** Lancio:

```bash
python -m agentic_rag.eval.esperimento esegui --etichetta finale --gt eval/ground_truth_finale --variante con:semantica=1 --variante senza:semantica=0 --ripetizioni 3 --judge --criterio "task_success_rate:con-senza>=10"
```

- Se si interrompe (rete, credito, PC), riprendi con la sola etichetta:

```bash
python -m agentic_rag.eval.esperimento esegui --etichetta finale --gt eval/ground_truth_finale
```

- [ ] **[insieme]** Controllo di validità sul riepilogo pubblico (`eval/reports/esperimenti/finale/riepilogo.md`, che Claude può leggere): esperimento **valido** (escluse ≤ 10% per variante), zero traceback, verdetto del criterio.
- Costo atteso: circa 0,012 $ per indagine col giudice, cioè circa 1,8 $ con 25 domande e 3,6 $ con 50.

## Fase 5 · Validazione del giudice (circa un'ora)

- [ ] **[tu]** `python -m agentic_rag.eval.esperimento etichette --etichetta finale --campione 30` crea un foglio privato con 30 risposte. Compilalo **alla cieca**: corretta / parziale / errata, senza guardare il verdetto del giudice.
- [ ] **[tu]** `python -m agentic_rag.eval.esperimento kappa --etichetta finale` calcola il κ di Cohen e lo aggiunge al riepilogo.
- Lettura: κ ≥ 0,6 vuol dire accordo buono e il giudice è affidabile; sotto, l'Answer Accuracy va presentata con cautela.

## Fase 6 · Risultati

- [ ] **[Claude]** README: tabella delle due varianti (Task Success Rate, Answer Accuracy, `errata`, cause inventate, costo e tempo per indagine) con intervalli al 95%, κ del giudice, criterio e verdetto.
- [ ] **[insieme]** La frase sul risultato, onesta:
  - se `con − senza < 10`: «la ricerca semantica non ha dato il miglioramento minimo richiesto (+10 punti); differenza X [IC]»; con la non-inferiorità provata: «la variante senza vettori non è inferiore di oltre 10 punti»;
  - se `≥ 10`: «la ricerca semantica migliora di X punti [IC]».
- [ ] **[Claude]** Prodotto: `RICERCA_SEMANTICA` impostata secondo il verdetto.
- [ ] **[tu]** CV e colloquio: dataset sintetico (62 documenti), set di sviluppo separato dal set finale, criterio fissato prima, κ del giudice, costo per indagine. Limiti dichiarati: un solo dataset, un modello (Haiku 5.5), un giudice LLM.

---

## Riepilogo dei tempi e dei costi

| Fase | Chi | Tempo | Costo |
|---|---|---|---|
| 0 Protezione | Claude | 10 min | 0 |
| 1 Decisioni | tu | 15 min | 0 |
| 2 Test set | tu | 3-5 h (25) · 6-10 h (50) | 0 |
| 3 Preparazione | tu + Claude | 30 min | 0 |
| 4 Esperimento | macchina | 1-4 h | 2-4 $ |
| 5 Giudice | tu | 1 h | 0 |
| 6 Risultati | Claude + tu | 1-2 h | 0 |
