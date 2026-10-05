# AGENTS.md

## Interaction Protocol
- Procedi autonomamente solo per task deterministici, modifiche circoscritte o refactoring evidenti.
- Per modifiche ad alto impatto con molteplici soluzioni valide o task architetturali o nuove feature complesse:
  - Non fare assunzioni rischiose.
  - Presenta brevemente i trade-off principali e fai qualche domanda mirata prima di generare il piano o toccare codice.


### Divieto Tassativo di Data Leakage (Anti-Cheating)
- L'agente e i moduli di reasoning applicativo **NON devono MAI accedere o consultare** i file in `eval/ground_truth/` (`storie.yaml`, `domande_test.yaml`) durante l'analisi, lo sviluppo dell'agente o l'elaborazione delle risposte.
- I file in `eval/ground_truth/` sono **esclusivamente riservati alla pipeline di benchmarking e test automatizzato** per confrontare le risposte fornite dall'agente con quelle attese.

## Principi Guida dell'Agente
1. **I numeri non si inventano:** calcoli, aggregazioni e confronti periodici passano **sempre ed esclusivamente** da query SQL in sola lettura (database relazionale). L'agente non calcola a mente né stima cifre nei prompt.
2. **Fonti obbligatorie e verificabili:** ogni conclusione o affermazione economica deve essere corredata dagli ID univoci delle fonti a supporto (`FATT-*`, `CTR-*`, `DOC-*`, `MOV-*`, ecc.), per permettere al commercialista di aprire e controllare il dato.
3. **Onestà sulle cause non documentate:** se un'anomalia o variazione numerica non trova riscontro nei documenti (es. il picco di spese trasferte di novembre), l'agente deve dichiarare esplicitamente che la causa non è documentata nelle fonti, astenendosi da congetture o invenzioni.
4. **Trasparenza del ragionamento:** l'agente deve rendere visibili i passaggi intermedi dell'indagine (query eseguite, documenti estratti tramite RAG) per consentire all'utente di validare il percorso logico.

