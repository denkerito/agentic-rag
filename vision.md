# Vision

> Un agente AI che **investiga autonomamente** i dati economici di un'azienda, collegando dati strutturati e documenti, per trasformarli in informazioni che un commercialista può **verificare e utilizzare**.

---

## Il problema

Nello studio di un commercialista le informazioni su un'azienda cliente sono sparpagliate: fatture, movimenti bancari, contratti, scadenze, dati contabili, comunicazioni. Rispondere a una domanda come *"perché il margine è calato ad agosto?"* richiede di:

1. estrarre i numeri da più fonti;
2. confrontarli tra periodi;
3. individuare le voci responsabili;
4. cercare i documenti che spiegano la variazione;
5. mettere insieme il tutto in una conclusione difendibile.

Il lavoro è lungo, ripetitivo e poco automatizzabile con strumenti tradizionali, perché ogni domanda richiede un percorso di analisi diverso.

## La proposta

Un agente che svolge **l'analisi preliminare** al posto del commercialista, e gliela consegna già verificabile.

```
Commercialista ──► domanda / situazione da analizzare
                        │
                        ▼
                     AGENTE ──► dati strutturati (SQL) + documenti (RAG)
                        │
                        ▼
                  analisi in più passi
                        │
                        ▼
Commercialista ◄── conclusione + numeri + fonti citate
```

Non sostituisce il commercialista. Gli fa risparmiare la fase di raccolta e confronto, e lascia a lui la parte che richiede giudizio professionale: **verificare e decidere**.

### Esempio

> **Domanda:** "Perché il margine è diminuito ad agosto?"

L'agente non risponde con una supposizione. Procede così:

1. recupera ricavi e costi di agosto;
2. li confronta con luglio;
3. identifica che i costi sono cresciuti più dei ricavi;
4. individua le categorie di costo responsabili;
5. recupera fatture e documenti collegati tramite RAG;
6. cerca una spiegazione nei documenti;
7. restituisce la risposta con le fonti.

> **Risposta:** "Il margine è diminuito principalmente per l'aumento dei costi software (+34%). Ho individuato un aumento del canone Microsoft a partire da giugno, supportato dalle fatture X e Y e dal contratto Z."

## Cosa rende il progetto diverso da un chatbot sui documenti

| Chatbot / RAG semplice | Questo progetto |
|---|---|
| Cerca testo simile alla domanda | Pianifica un percorso di analisi |
| Una sola chiamata di recupero | Più passi, ciascuno basato sul risultato del precedente |
| Il LLM "calcola" i numeri | I numeri vengono **sempre** da query SQL, mai dal modello |
| Risposta fluida, fonti opzionali | Ogni affermazione è collegata a un dato o a un documento |
| Risponde sempre | Dice "non ho trovato una causa" quando è il caso |

L'ultimo punto è centrale: in un contesto contabile una risposta sbagliata ma convincente è peggio di nessuna risposta.

## Principi di progetto

1. **Verificabilità prima di tutto.** Ogni conclusione riporta numeri e fonti (ID fattura, contratto, movimento) che il commercialista può aprire e controllare.
2. **I numeri non si inventano.** Calcoli e aggregazioni passano da SQL in sola lettura. Il LLM interpreta e collega, non calcola.
3. **Onestà sull'incertezza.** L'agente espone un livello di confidenza e distingue ciò che è provato dai documenti da ciò che è ipotesi.
4. **Il ragionamento è visibile.** I passi dell'agente (query eseguite, documenti consultati) sono mostrati nell'interfaccia: è così che il commercialista si fida.
5. **Human in the loop.** L'agente prepara, l'umano controlla e decide. Nessuna azione viene eseguita in autonomia sui dati.

## Ambito dell'MVP

### Incluso

- Un'azienda fittizia con 12 mesi di dati sintetici (circa 300 movimenti, fatture, contratti).
- Dati strutturati: movimenti bancari, fatture (anche in formato XML FatturaPA), fornitori, categorie di costo, scadenze.
- Documenti non strutturati: contratti e comunicazioni, indicizzati per la ricerca semantica.
- Un agente con strumenti per interrogare il database, cercare nei documenti, confrontare periodi e aprire un documento specifico.
- Interfaccia con domanda, passi di ragionamento in tempo reale, risposta e fonti.
- Un piccolo set di domande di test con risposta attesa, per misurare se l'agente trova ciò che deve trovare.

### Escluso (volutamente)

- Dati reali di clienti: per ragioni di privacy il progetto usa solo dati sintetici.
- Integrazione con gestionali, SdI o open banking.
- Autenticazione, multi-azienda, multi-utente.
- Qualsiasi scrittura sui dati contabili.
- Modalità proattiva (segnalazione automatica di anomalie): possibile evoluzione futura, non parte dell'MVP.

## Dati sintetici: le "storie nascoste"

La qualità della demo dipende dai dati. Invece di generare numeri casuali, si costruiscono **storie** da far scoprire all'agente, ad esempio:

- **Aumento del canone software:** un fornitore alza il canone da giugno; il contratto lo prevede, e le fatture lo confermano.
- **Costo anomalo non ricorrente:** una consulenza una tantum spiega un picco di costi in un mese.
- **Calo dei ricavi per un cliente:** un cliente importante riduce gli ordini; la causa è visibile nelle comunicazioni.
- **Caso senza spiegazione:** una variazione che nei dati non ha una causa documentata, per verificare che l'agente lo ammetta invece di inventare.

Ogni storia ha una domanda associata e una risposta attesa: sono il test di valutazione del progetto.

## Architettura

```
┌────────────┐     ┌──────────────────────────────────────┐
│     UI     │◄───►│               Agente                 │
│ (React)│     │  loop: pianifica → usa tool → valuta │
└────────────┘     └───────┬───────────┬───────────┬──────┘
                           │           │           │
                  query_sql   cerca_documenti   confronta_periodi
                           │           │
                    ┌──────▼───┐  ┌────▼─────────┐
                    │          │  │ Vector store │
                    │ (dati    │  │ (contratti,  │
                    │ struttur)│  │ comunicaz.)  │
                    └──────────┘  └──────────────┘
```

### Stack proposto

| Livello | Scelta | Motivo |
|---|---|---|
| Linguaggio | Python | Standard per il lavoro con LLM |
| Orchestrazione agente | **Pydantic AI** | Il percorso di analisi è deciso dal modello (loop con tool); output tipizzato e validato (fonti obbligatorie, confidenza, causa documentata), dipendenze iniettate nei tool, test senza chiamate LLM (`TestModel`). Se in futuro servirà un flusso fisso, human-in-the-loop o modalità proattiva, si può passare a `pydantic-graph` o rivalutare LangGraph |
| LLM | Gemini (API gratuita) con function calling | Costo zero per l'MVP; i limiti del piano gratuito vanno verificati prima di iniziare |
| Dati strutturati | PostgreSQL |  |
| Vector store | pgvector |  |
| Backend | FastAPI | Espone l'agente e fa lo streaming dei passi |
| Frontend | React | Il più rapido per un'interfaccia con stream dei passi; il frontend non è il punto del progetto |
| Osservabilità | Logfire (piano gratuito, integrazione nativa con Pydantic AI) o log strutturati | Rende visibile il ragionamento, utile anche nel portfolio |

## Come si misura il successo

- **Recall sulle storie nascoste:** su N domande di test, quante volte l'agente individua la causa corretta.
- **Accuratezza dei numeri:** i valori citati coincidono con quelli del database (dovrebbe essere sempre, per costruzione).
- **Qualità delle fonti:** ogni fonte citata esiste e supporta davvero l'affermazione.
- **Onestà:** sul caso senza spiegazione, l'agente dichiara di non averla trovata.
- **Costo per domanda:** numero di chiamate al modello per investigazione, per restare dentro i limiti gratuiti.

## Roadmap

| Giorno | Obiettivo |
|---|---|
| 1 | Generatore di dati sintetici con le storie nascoste; schema del database |
| 2 | Parsing fatture XML, indicizzazione dei documenti |
| 3 | Agente con strumenti; caso "margine di agosto" funzionante end to end |
| 4 | Citazione delle fonti, gestione dell'incertezza, interfaccia con passi in tempo reale |
| 5 | Valutazione sulle domande di test, rifinitura, README, demo registrata |

## Evoluzioni possibili

- **Modalità proattiva:** l'agente analizza i dati senza domanda e segnala anomalie (fatture duplicate, movimenti senza fattura, scadenze senza liquidità).
- **Verifica contratto contro realtà:** confronto sistematico tra clausole contrattuali e importi effettivamente fatturati.
- **Multi-azienda** e memoria delle investigazioni precedenti.
- **Integrazione con un gestionale reale** tramite i suoi export.
