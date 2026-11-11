# Esperimento finale

- creato: 2026-10-26T14:10:42+01:00 · codice `src` 2c20f01d0c
- ripetizioni: 3 · domande: 50
- giudice: openrouter:anthropic/claude-sonnet-5.5
- costo: 2.8996 $ (agente 1.4276 $, giudice 1.4720 $) su 300 esecuzioni
- variante `senza`: modello openrouter:anthropic/claude-haiku-5.5, semantica False
- variante `con`: modello openrouter:anthropic/claude-haiku-5.5, semantica True

Esperimento **valido**.

**Criterio** `task_success_rate: con − senza ≥ 10 punti` → **non supera** (+0.7 punti, IC 95% [-2.0, 3.3])

## Metriche (media sulle domande, IC 95% bootstrap)

| Metrica | senza | con |
|---|---|---|
| Task Success Rate | 93.3% [87.3, 98.0] · n=150 | 94.0% [88.0, 98.7] · n=150 |
| Answer Accuracy (LLM-as-a-judge) | 92.3% [87.7, 96.3] · n=148 | 93.3% [87.3, 98.0] · n=147 |
|   di cui parziali | 7.7% [3.7, 12.3] · n=148 | 6.7% [2.0, 12.7] · n=147 |
| Source Citation Recall | 98.4% [95.3, 100.0] · n=95 | 100.0% [100.0, 100.0] · n=94 |
| Numeric Exact Match Recall | 96.3% [89.8, 100.0] · n=107 | 96.8% [90.7, 100.0] · n=106 |
| False Acceptance Rate | 0.0% [0.0, 0.0] · n=29 | 0.0% [0.0, 0.0] · n=29 |
| False Abstention Rate | 65.0% [45.0, 85.0] · n=59 | 66.7% [46.6, 86.7] · n=58 |
| Guardrail Intervention Rate | 58.0% [48.0, 68.0] · n=150 | 59.3% [49.3, 70.0] · n=150 |
| Session Evidence Recall | 98.0% [94.0, 100.0] · n=74 | 100.0% [100.0, 100.0] · n=73 |
| pass^3 | 88.0% [78.0, 96.0] · domande=50 | 90.0% [80.0, 98.0] · domande=50 |

## Efficienza

| | senza | con |
|---|---|---|
| esecuzioni | 150 | 150 |
| token_input_medi | 81843 | 84242 |
| token_output_medi | 5284 | 5262 |
| richieste_medie | 6.3 | 6.2 |
| chiamate_tool_medie | 9.2 | 9.2 |
| lavoro_p50_s | 28.6 | 28.6 |
| lavoro_p95_s | 51.2 | 56.3 |
| attesa_media_s | 0.0 | 0.4 |
| tentativi_provider_medi | 0.0 | 0.0 |
| quota_input_da_cache | 86% | 87% |
| costo_medio_usd | 0.0048 $ | 0.0047 $ |
| costo_giudice_medio_usd | 0.0050 $ | 0.0050 $ |

## Esecuzioni

- `senza`: 150 chiuse (2 fallite per l'agente), 0 errori di infrastruttura registrati, 0 senza verdetto del giudice, rifiuti del validatore {'assenza_non_provata': 87, 'fonti_non_viste': 17, 'numeri_senza_fonti': 11}
- `con`: 150 chiuse (3 fallite per l'agente), 0 errori di infrastruttura registrati, 0 senza verdetto del giudice, rifiuti del validatore {'assenza_non_provata': 98, 'numeri_senza_fonti': 11, 'fonti_non_viste': 15}

## Confronti appaiati (differenza in punti, IC 95%)

| Metrica | con - senza |
|---|---|
| Task Success Rate | +0.7 [-2.0, +3.3] |
| Answer Accuracy (LLM-as-a-judge) | +1.0 [-4.0, +6.0] |
|   di cui parziali | -1.0 [-6.0, +4.0] |
| Source Citation Recall | +1.6 [+0.0, +4.7] |
| Numeric Exact Match Recall | +0.5 [-1.4, +2.8] |
| False Acceptance Rate | +0.0 [+0.0, +0.0] |
| False Abstention Rate | +1.7 [-5.0, +8.3] |
| Guardrail Intervention Rate | +1.3 [-8.0, +10.0] |
| Session Evidence Recall | +2.0 [+0.0, +6.0] |

## Validazione del giudice

Campione di 30 risposte etichettate a mano: κ di Cohen -0.05 (3 classi), -0.05 (corretta/non corretta), accordo 87%.

Note: le metriche sulla risposta si calcolano sulle esecuzioni completate; Task Success Rate, Guardrail Intervention Rate ed efficienza contano anche quelle fallite per l'agente. Pause e tentativi falliti del provider (429/5xx, rete) sono esclusi dal tempo di lavoro e inclusi nell'attesa media.
