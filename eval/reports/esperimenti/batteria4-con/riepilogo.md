# Esperimento batteria4-con

- creato: 2026-10-23T12:00:41+02:00 · codice `src` 41248009ea
- ripetizioni: 2 · domande: 12
- giudice: openrouter:anthropic/claude-sonnet-5.5
- costo: 0.2832 $ (agente 0.1547 $, giudice 0.1285 $) su 24 esecuzioni
- variante `con`: modello openrouter:anthropic/claude-haiku-5.5, semantica True

Esperimento **valido**.

## Metriche (media sulle domande, IC 95% bootstrap)

| Metrica | con |
|---|---|
| Task Success Rate | 66.7% [41.7, 87.5] · n=24 |
| Answer Accuracy (LLM-as-a-judge) | 91.7% [79.2, 100.0] · n=23 |
|   di cui parziali | 8.3% [0.0, 20.8] · n=23 |
| Source Citation Recall | 92.3% [84.2, 99.0] · n=19 |
| Numeric Exact Match Recall | 97.5% [92.5, 100.0] · n=19 |
| False Acceptance Rate | 0.0% [0.0, 0.0] · n=4 |
| False Abstention Rate | 12.5% [0.0, 37.5] · n=15 |
| Guardrail Intervention Rate | 62.5% [41.7, 83.3] · n=24 |
| Session Evidence Recall | 92.6% [85.2, 100.0] · n=17 |
| pass^3 | n/a · domande=0 |

## Efficienza

| | con |
|---|---|
| esecuzioni | 24 |
| token_input_medi | 111864 |
| token_output_medi | 7109 |
| richieste_medie | 7.3 |
| chiamate_tool_medie | 10.4 |
| lavoro_p50_s | 38.6 |
| lavoro_p95_s | 56.7 |
| attesa_media_s | 0.0 |
| tentativi_provider_medi | 0.0 |
| quota_input_da_cache | 86% |
| costo_medio_usd | 0.0064 $ |
| costo_giudice_medio_usd | 0.0056 $ |

## Esecuzioni

- `con`: 24 chiuse (1 fallite per l'agente), 0 errori di infrastruttura registrati, 0 senza verdetto del giudice, rifiuti del validatore {'fonti_non_viste': 11, 'assenza_non_provata': 14, 'numeri_senza_fonti': 4}

Note: le metriche sulla risposta si calcolano sulle esecuzioni completate; Task Success Rate, Guardrail Intervention Rate ed efficienza contano anche quelle fallite per l'agente. Pause e tentativi falliti del provider (429/5xx, rete) sono esclusi dal tempo di lavoro e inclusi nell'attesa media.
