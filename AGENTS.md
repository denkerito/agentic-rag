# AGENTS.md

## Interaction Protocol
- Procedi autonomamente solo per task deterministici, modifiche circoscritte o refactoring evidenti.
- Per modifiche ad alto impatto con molteplici soluzioni valide o task architetturali o nuove feature complesse:
  - Non fare assunzioni rischiose.
  - Presenta brevemente i trade-off principali e fai qualche domanda mirata prima di generare il piano o toccare codice.

## Ground truth
- Le 12 domande in `eval/ground_truth/` sono il set di sviluppo.
- Le 50 domande in `eval/ground_truth_finale/` sono il test set dell'esperimento `finale` (2026-10-26). Sono rimaste vietate all'assistente fino alla fine dell'esperimento e della validazione del giudice. Dal 2026-11-11 sono visibili e in git, quindi non misurano più nulla di nuovo: non si usano per ritoccare prompt, soglie, tool o metriche, e una modifica futura all'agente va misurata su un test set nuovo.
- Un test set nuovo ha la stessa protezione fino alla fine del suo esperimento. La sua cartella e i report privati delle etichette che la usano (`eval/reports/private/esperimenti/`) non si aprono, non si leggono e non se ne stampa il contenuto: l'assistente ne conosce solo la struttura. Il codice dell'harness li legge a runtime, e all'assistente arrivano solo output di conteggi (es. `tools/controlla_ground_truth.py`) e i report pubblici.
- L'agente e i moduli applicativi non accedono mai ai file di ground truth.

## Principi Guida dell'Agente
1. **I numeri non si inventano:** calcoli, aggregazioni e confronti periodici passano **sempre ed esclusivamente** da query SQL in sola lettura (database relazionale). L'agente non calcola a mente né stima cifre nei prompt.
2. **Fonti obbligatorie e verificabili:** ogni conclusione o affermazione economica deve essere corredata dagli ID univoci delle fonti a supporto (`FATT-*`, `CTR-*`, `DOC-*`, `MOV-*`, ecc.), per permettere al commercialista di aprire e controllare il dato.
3. **Onestà sulle cause non documentate:** se un'anomalia o variazione numerica non trova riscontro nei documenti (es. il picco di spese trasferte di novembre), l'agente deve dichiarare esplicitamente che la causa non è documentata nelle fonti, astenendosi da congetture o invenzioni.
4. **Trasparenza del ragionamento:** l'agente deve rendere visibili i passaggi intermedi dell'indagine (query eseguite, documenti estratti tramite RAG) per consentire all'utente di validare il percorso logico.

