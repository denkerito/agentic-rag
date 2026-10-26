# Esperimento collaudo-v1

- creato: 2026-10-26T14:04:09+01:00 · codice `src` 2c20f01d0c
- ripetizioni: 1 · domande: 2
- giudice: openrouter:anthropic/claude-sonnet-5.5
- costo: 0.0603 $ (agente 0.0373 $, giudice 0.0230 $) su 4 esecuzioni
- variante `senza`: modello openrouter:anthropic/claude-haiku-5.5, semantica False
- variante `con`: modello openrouter:anthropic/claude-haiku-5.5, semantica True

Esperimento **valido**.

## Metriche (media sulle domande, IC 95% bootstrap)

| Metrica | senza | con |
|---|---|---|
| Task Success Rate | 50.0% [0.0, 100.0] · n=2 | 50.0% [0.0, 100.0] · n=2 |
| Answer Accuracy (LLM-as-a-judge) | 100.0% [100.0, 100.0] · n=2 | 100.0% [100.0, 100.0] · n=2 |
|   di cui parziali | 0.0% [0.0, 0.0] · n=2 | 0.0% [0.0, 0.0] · n=2 |
| Source Citation Recall | 91.7% [83.3, 100.0] · n=2 | 83.3% [66.7, 100.0] · n=2 |
| Numeric Exact Match Recall | 100.0% [100.0, 100.0] · n=2 | 66.7% [33.3, 100.0] · n=2 |
| False Acceptance Rate | 0.0% [0.0, 0.0] · n=1 | 0.0% [0.0, 0.0] · n=1 |
| False Abstention Rate | 0.0% [0.0, 0.0] · n=1 | 0.0% [0.0, 0.0] · n=1 |
| Guardrail Intervention Rate | 50.0% [0.0, 100.0] · n=2 | 100.0% [100.0, 100.0] · n=2 |
| Session Evidence Recall | 75.0% [75.0, 75.0] · n=1 | 50.0% [50.0, 50.0] · n=1 |
| pass^3 | n/a · domande=0 | n/a · domande=0 |

## Efficienza

| | senza | con |
|---|---|---|
| esecuzioni | 2 | 2 |
| token_input_medi | 176910 | 157910 |
| token_output_medi | 10614 | 8706 |
| richieste_medie | 8.5 | 9.0 |
| chiamate_tool_medie | 14.0 | 13.0 |
| lavoro_p50_s | 49.7 | 47.5 |
| lavoro_p95_s | 67.1 | 51.8 |
| attesa_media_s | 0.0 | 0.0 |
| tentativi_provider_medi | 0.0 | 0.0 |
| quota_input_da_cache | 85% | 86% |
| costo_medio_usd | 0.0101 $ | 0.0085 $ |
| costo_giudice_medio_usd | 0.0056 $ | 0.0059 $ |

## Esecuzioni

- `senza`: 2 chiuse (0 fallite per l'agente), 0 errori di infrastruttura registrati, 0 senza verdetto del giudice, rifiuti del validatore {'fonti_non_viste': 2, 'assenza_non_provata': 1}
- `con`: 2 chiuse (0 fallite per l'agente), 0 errori di infrastruttura registrati, 0 senza verdetto del giudice, rifiuti del validatore {'fonti_non_viste': 1, 'assenza_non_provata': 2}

## Confronti appaiati (differenza in punti, IC 95%)

| Metrica | con - senza |
|---|---|
| Task Success Rate | +0.0 [+0.0, +0.0] |
| Answer Accuracy (LLM-as-a-judge) | +0.0 [+0.0, +0.0] |
|   di cui parziali | +0.0 [+0.0, +0.0] |
| Source Citation Recall | -8.3 [-16.7, +0.0] |
| Numeric Exact Match Recall | -33.3 [-66.7, +0.0] |
| False Acceptance Rate | +0.0 [+0.0, +0.0] |
| False Abstention Rate | +0.0 [+0.0, +0.0] |
| Guardrail Intervention Rate | +50.0 [+0.0, +100.0] |
| Session Evidence Recall | -25.0 [-25.0, -25.0] |

Note: le metriche sulla risposta si calcolano sulle esecuzioni completate; Task Success Rate, Guardrail Intervention Rate ed efficienza contano anche quelle fallite per l'agente. Pause e tentativi falliti del provider (429/5xx, rete) sono esclusi dal tempo di lavoro e inclusi nell'attesa media.
