# Esperimento batteria-con

- creato: 2026-10-22T12:13:46+02:00 · codice `src` b6f7d79293
- ripetizioni: 1 · domande: 12
- giudice: openrouter:anthropic/claude-sonnet-5.5
- costo: 0.1125 $ (agente 0.0485 $, giudice 0.0640 $) su 12 esecuzioni
- variante `con`: modello openrouter:anthropic/claude-haiku-5.5, semantica True

Esperimento **valido**.

## Metriche (media sulle domande, IC 95% bootstrap)

| Metrica | con |
|---|---|
| Task Success Rate | 33.3% [8.3, 58.3] · n=12 |
| Answer Accuracy (LLM-as-a-judge) | 58.3% [33.3, 83.3] · n=12 |
|   di cui parziali | 41.7% [16.7, 66.7] · n=12 |
| Source Citation Recall | 73.8% [50.8, 93.0] · n=10 |
| Numeric Exact Match Recall | 64.1% [36.8, 92.6] · n=9 |
| False Acceptance Rate | 0.0% [0.0, 0.0] · n=2 |
| False Abstention Rate | 12.5% [0.0, 37.5] · n=8 |
| Guardrail Intervention Rate | 41.7% [16.7, 66.7] · n=12 |
| Session Evidence Recall | 76.9% [57.4, 92.6] · n=9 |
| pass^3 | n/a · domande=0 |

## Efficienza

| | con |
|---|---|
| esecuzioni | 12 |
| token_input_medi | 65195 |
| token_output_medi | 4383 |
| richieste_medie | 5.7 |
| chiamate_tool_medie | 7.7 |
| lavoro_p50_s | 24.9 |
| lavoro_p95_s | 38.8 |
| attesa_media_s | 0.0 |
| tentativi_provider_medi | 0.0 |
| quota_input_da_cache | 84% |
| costo_medio_usd | 0.0040 $ |
| costo_giudice_medio_usd | 0.0053 $ |

## Esecuzioni

- `con`: 12 chiuse (0 fallite per l'agente), 0 errori di infrastruttura registrati, 0 senza verdetto del giudice, rifiuti del validatore {'fonti_non_viste': 3, 'numeri_senza_fonti': 4}

Note: le metriche sulla risposta si calcolano sulle esecuzioni completate; Task Success Rate, Guardrail Intervention Rate ed efficienza contano anche quelle fallite per l'agente. Pause e tentativi falliti del provider (429/5xx, rete) sono esclusi dal tempo di lavoro e inclusi nell'attesa media.
