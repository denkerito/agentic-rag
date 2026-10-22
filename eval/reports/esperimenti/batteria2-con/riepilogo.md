# Esperimento batteria2-con

- creato: 2026-10-22T13:19:51+02:00 · codice `src` d5fdc6ba35
- ripetizioni: 1 · domande: 12
- giudice: openrouter:anthropic/claude-sonnet-5.5
- costo: 0.1064 $ (agente 0.0480 $, giudice 0.0584 $) su 12 esecuzioni
- variante `con`: modello openrouter:anthropic/claude-haiku-5.5, semantica True

Esperimento **valido**.

## Metriche (media sulle domande, IC 95% bootstrap)

| Metrica | con |
|---|---|
| Task Success Rate | 33.3% [8.3, 58.3] · n=12 |
| Answer Accuracy (LLM-as-a-judge) | 72.7% [45.5, 100.0] · n=11 |
|   di cui parziali | 27.3% [0.0, 54.5] · n=11 |
| Source Citation Recall | 70.4% [46.3, 92.6] · n=9 |
| Numeric Exact Match Recall | 73.2% [48.5, 93.8] · n=8 |
| False Acceptance Rate | 0.0% [0.0, 0.0] · n=2 |
| False Abstention Rate | 28.6% [0.0, 57.1] · n=7 |
| Guardrail Intervention Rate | 33.3% [8.3, 58.3] · n=12 |
| Session Evidence Recall | 69.8% [40.6, 91.7] · n=8 |
| pass^3 | n/a · domande=0 |

## Efficienza

| | con |
|---|---|
| esecuzioni | 12 |
| token_input_medi | 67130 |
| token_output_medi | 4274 |
| richieste_medie | 5.5 |
| chiamate_tool_medie | 7.5 |
| lavoro_p50_s | 20.6 |
| lavoro_p95_s | 38.4 |
| attesa_media_s | 0.0 |
| tentativi_provider_medi | 0.0 |
| quota_input_da_cache | 85% |
| costo_medio_usd | 0.0040 $ |
| costo_giudice_medio_usd | 0.0053 $ |

## Esecuzioni

- `con`: 12 chiuse (1 fallite per l'agente), 0 errori di infrastruttura registrati, 0 senza verdetto del giudice, rifiuti del validatore {'fonti_non_viste': 5, 'numeri_senza_fonti': 1}

Note: le metriche sulla risposta si calcolano sulle esecuzioni completate; Task Success Rate, Guardrail Intervention Rate ed efficienza contano anche quelle fallite per l'agente. Pause e tentativi falliti del provider (429/5xx, rete) sono esclusi dal tempo di lavoro e inclusi nell'attesa media.
