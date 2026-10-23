# I tuoi passi: dal test set nuovo ai risultati

Solo ciò che fai tu. Le parti di Claude (regola in AGENTS.md, congelamento, README) sono nella guida completa: [2026-10-23-test-set-finale.md](2026-10-23-test-set-finale.md).

Decisioni già prese (2026-10-23): **50-60 domande**, **Task Success Rate e Answer Accuracy con lo stesso peso** (il criterio di decisione resta TSR +10 punti), **non-inferiorità sì**.

> **Regola d'oro, per tutto il percorso:** non incollare mai in chat domande, risposte attese, query attese o pezzi dei report privati del set finale. A Claude mostri solo l'output dei comandi di controllo (conteggi) e i report **pubblici**.

---

## Passo 1 · Prima di iniziare (5 minuti)

1. Aspetta che Claude abbia fatto la **fase 0**: regola in `AGENTS.md` e `eval/ground_truth_finale/` nel `.gitignore`.
2. Controlla che la cartella non finisca in git:
   ```bash
   git check-ignore eval/ground_truth_finale/domande_test.yaml
   ```
   Deve stampare il percorso. Se non stampa nulla, fermati e chiedi a Claude.
3. Crea la cartella e i due file vuoti: `eval/ground_truth_finale/domande_test.yaml` e `storie.yaml`.

## Passo 2 · Prepararsi a scrivere (30-60 minuti)

**Dove guardare i dati, senza usare l'agente:**
- numeri: i CSV in `data/csv/` (fatture, righe fattura, movimenti, scritture, scadenzario, contratti, clienti, fornitori, piano dei conti). Apribili con un foglio di calcolo;
- documenti: `data/index.csv` (ID, tipo, data, titolo, controparte) e i testi in `data/documenti/`;
- in alternativa il database, con le credenziali di `DATABASE_URL` nel `.env`.

**Scegli gli argomenti.** Il dataset è lo stesso del set di sviluppo, quindi le 6 storie si possono riusare, **ma con domande diverse**: altri periodi, altri clienti o fornitori, altri angoli (per esempio «quando scade il preavviso del contratto Y?» invece di «perché è aumentato il canone?»). Cerca anche fatti non coperti dalle storie: variazioni piccole, scadenze, pagamenti, contratti.

**Prepara una tabella di lavoro** (foglio o file personale, **fuori dal repository**): id, modalità, argomento, fonti decisive, numeri attesi. Ti serve per tenere la distribuzione.

## Passo 3 · Distribuzione da rispettare

Obiettivo **50 domande** (fino a 60 se ti vengono bene):

| Modalità | Quante | Come si ottiene nel campo `tipo` |
|---|---|---|
| normale: causa documentata, numeri, confronti | 30 | qualunque testo senza le parole sotto, es. `"multi-passo"`, `"recupero + numero"` |
| normale con risposta corretta **«no»** | 6 | come sopra, es. `"verifica: risposta negativa"` |
| onesta: causa **non** documentata | 6 | deve contenere `non documentata` |
| non rispondibile | 4 | deve contenere `non rispondibile` |
| regolare: nessuna anomalia | 4 | deve contenere `regolare` |

Nelle 30 normali, mescola:
- cause con **un solo** documento decisivo e cause con **due o più** documenti;
- domande **solo numeriche** (quanto, quando, chi) senza causa;
- **confronti** tra periodi (mesi, trimestri) diversi da quelli già usati;
- **controlli contabili** (pagamenti, scadenze, coerenza tra fattura e movimento);
- **contratti** (durata, preavviso, canone, rinnovo).

## Passo 4 · Scrivere ogni domanda (la parte lunga: 6-9 ore, anche in più sessioni)

Per **ogni** domanda, in quest'ordine:

1. **Formula la domanda** come la farebbe un commercialista, in una frase, senza indizi sulla risposta.
2. **Trova la risposta nei dati**, a mano (CSV, documenti, DB). Annota gli ID decisivi.
3. **Scrivi `risposta_attesa`:** la causa o l'esito e i numeri essenziali. Per le onesta scrivi esplicitamente «la causa non è documentata»; per le non rispondibili «non è possibile rispondere con i dati disponibili»; per le «no» la risposta negativa e su cosa si basa.
4. **Scrivi `fonti_attese`:** solo le fonti **necessarie**, cioè il documento che prova la causa e le fatture o i movimenti decisivi. Niente documenti di contorno: una risposta che cita tutte le fonti elencate deve essere completa. Aggiungi `nome.csv` **solo** se l'unico modo di rispondere passa da quella tabella.
5. **Scrivi `query_sql`,** che gira su SQLite costruito dai CSV, con le colonne dei CSV e `strftime` per le date:
   - restituisce **solo i numeri che la risposta deve contenere**: niente colonne di contorno (IVA, totali, conteggi non chiesti);
   - **al massimo 25 valori**, e mai elenchi lunghi;
   - codici come testo (`categoria = '64.01'`);
   - per le onesta e le non rispondibili può mancare (`query_sql: ""`).
6. **Prova la query** esattamente come la eseguirà l'harness (salva la query in un file temporaneo **fuori dal repository**):
   ```bash
   python -c "from agentic_rag.eval.numeri import esegui_query_attesa as q; r = q(open(r'C:\percorso\query.sql', encoding='utf-8').read()); print(r.errore, r.n_righe, sorted(r.valori))"
   ```
   Errore `None`, e i valori devono essere **proprio** i numeri che hai scritto nella risposta attesa.
7. **Coerenza:** risposta attesa e query dicono la stessa cosa, con la stessa granularità (se la query è per singolo conto, anche la risposta lo è).
8. **Controllo dei fatti:** ogni ID citato esiste, ed è del periodo e della controparte giusti. Ogni numero della risposta attesa è quello dei dati.
9. **Mai** provare la domanda sull'agente, né nella UI né con l'eval.

Formato di una voce (valori inventati):

```yaml
domande:
  - id: 1
    domanda: "Perché i costi di X sono saliti a maggio?"
    storia_id: "ST-01"
    tipo: "multi-passo"
    risposta_attesa: >
      Testo della risposta corretta, con causa e numeri essenziali.
    fonti_attese:
      - "DOC-EML-999"
      - "FATT-P-2025-9999"
    query_sql: >
      SELECT ...
```

Gli `id` sono numeri unici, da 1 in su. `storia_id` è opzionale; se usi un ID di storia (`ST-07`…), aggiungilo in `storie.yaml` con `id` e `titolo`.

## Passo 5 · Verifiche finali (30-60 minuti)

1. Validazione dell'harness:
   ```bash
   python -m agentic_rag.eval --dry-run --gt eval/ground_truth_finale
   ```
   Tutte le query `ok` (o `assente` dove previsto) e 0 fonti non riconosciute.
2. Controllo strutturale, che stampa solo conteggi:
   ```bash
   python tools/controlla_ground_truth.py eval/ground_truth_finale
   ```
   Deve dare `domande da controllare: 0` e la distribuzione del passo 3. Le righe con `<-- controlla` vanno sistemate: ID inesistenti, query in errore, query senza numeri o con più di 25 valori.
3. **Questo output lo puoi incollare a Claude**: contiene solo numeri.
4. Rilettura finale a mente fresca: per ogni domanda, «una risposta che dice esattamente la risposta attesa e cita le fonti attese è giusta e completa?».
5. Da qui il set è **congelato**: non si modifica più, neanche dopo i risultati.

## Passo 6 · Preparare l'esperimento (20 minuti)

1. **Gemini:** in Google AI Studio passa al piano a pagamento per il progetto della chiave `GOOGLE_API_KEY` e imposta un limite di spesa (per esempio 2 $). Gli embedding costano frazioni di centesimo.
2. **OpenRouter:** sulla chiave `OPENROUTER_API_KEY` imposta un limite di credito di 8 $ e controlla di avere almeno 6 $ di saldo (stima per 50 domande: circa 3,6 $).
3. Di' a Claude che il set è pronto: fa il congelamento (test verdi, tag `eval-v1`).
4. PC collegato alla corrente, sospensione disattivata per 3-4 ore, connessione stabile.

## Passo 7 · Lanciare e seguire l'esperimento (3-4 ore di macchina)

1. Lancio (oppure lo chiedi a Claude):
   ```bash
   python -m agentic_rag.eval.esperimento esegui --etichetta finale --gt eval/ground_truth_finale --variante con:semantica=1 --variante senza:semantica=0 --ripetizioni 3 --judge --criterio "task_success_rate:con-senza>=10"
   ```
2. Se si interrompe (rete, credito, riavvio), riprendi con:
   ```bash
   python -m agentic_rag.eval.esperimento esegui --etichetta finale --gt eval/ground_truth_finale
   ```
3. Alla fine leggi `eval/reports/esperimenti/finale/riepilogo.md` (pubblico, lo puoi condividere con Claude). Controlla che dica **«Esperimento valido»**, con escluse al massimo il 10% per variante.

## Passo 8 · Validare il giudice (circa un'ora)

1. Genera il foglio:
   ```bash
   python -m agentic_rag.eval.esperimento etichette --etichetta finale --campione 30
   ```
2. Apri il foglio privato indicato dal comando e, per ognuna delle 30 risposte, scrivi `corretta`, `parziale` o `errata` confrontandola con la risposta attesa. **Alla cieca:** senza guardare il verdetto del giudice. Usa gli stessi criteri del giudice:
   - **corretta:** stessa causa o esito e dati essenziali;
   - **parziale:** solo una parte, oppure corretta ma incompleta;
   - **errata:** causa diversa, contraddizione, oppure una causa inventata dove la risposta attesa dice «non documentata».
3. Calcola l'accordo:
   ```bash
   python -m agentic_rag.eval.esperimento kappa --etichetta finale
   ```
   Un κ ≥ 0,6 indica un giudice affidabile. Sotto, l'Answer Accuracy va presentata con cautela.

## Passo 9 · Risultati e CV (1 ora, con Claude)

1. Rileggi la tabella del README che prepara Claude: due varianti, intervalli, κ, costo per indagine.
2. Scegli la frase sul risultato in base al verdetto:
   - con − senza < 10 e limite superiore dell'IC < 10: «la variante senza vettori **non è inferiore** di oltre 10 punti»;
   - con − senza < 10, ma intervallo largo: «la ricerca semantica **non ha dato il miglioramento richiesto** (+10 punti)»;
   - con − senza ≥ 10: «la ricerca semantica **migliora** di X punti».
3. Per il CV e il colloquio:
   - set di sviluppo separato dal set finale;
   - criterio fissato prima;
   - κ del giudice;
   - costo per indagine;
   - limiti: dati sintetici (62 documenti), un modello, un giudice LLM.

---

## Checklist rapida

- [ ] Fase 0 fatta da Claude; `git check-ignore` ok
- [ ] Cartella e file creati
- [ ] Tabella di lavoro con la distribuzione (fuori dal repository)
- [ ] 50-60 domande scritte, con ogni query provata
- [ ] `--dry-run` ok
- [ ] `controlla_ground_truth.py`: 0 da controllare, distribuzione giusta
- [ ] Set congelato
- [ ] Fatturazione Gemini attiva, limite di credito su OpenRouter, saldo sufficiente
- [ ] Congelamento del codice (Claude)
- [ ] Esperimento lanciato e «valido»
- [ ] 30 etichette alla cieca e κ calcolato
- [ ] Frase sul risultato e README
