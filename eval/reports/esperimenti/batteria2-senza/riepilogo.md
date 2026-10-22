# Esperimento batteria2-senza

- creato: 2026-10-22T13:12:57+02:00 · codice `src` d5fdc6ba35
- ripetizioni: 1 · domande: 12
- giudice: openrouter:anthropic/claude-sonnet-5.5
- costo: 0.1222 $ (agente 0.0583 $, giudice 0.0639 $) su 12 esecuzioni
- variante `senza`: modello openrouter:anthropic/claude-haiku-5.5, semantica False

Esperimento **valido**.

## Metriche (media sulle domande, IC 95% bootstrap)

| Metrica | senza |
|---|---|
| Task Success Rate | 16.7% [0.0, 41.7] · n=12 |
| Answer Accuracy (LLM-as-a-judge) | 83.3% [58.3, 100.0] · n=12 |
|   di cui parziali | 16.7% [0.0, 41.7] · n=12 |
| Source Citation Recall | 75.8% [53.3, 94.2] · n=10 |
| Numeric Exact Match Recall | 70.0% [48.1, 89.8] · n=9 |
| False Acceptance Rate | 0.0% [0.0, 0.0] · n=2 |
| False Abstention Rate | 12.5% [0.0, 37.5] · n=8 |
| Guardrail Intervention Rate | 33.3% [8.3, 58.3] · n=12 |
| Session Evidence Recall | 77.8% [61.1, 94.4] · n=9 |
| pass^3 | n/a · domande=0 |

## Efficienza

| | senza |
|---|---|
| esecuzioni | 12 |
| token_input_medi | 84682 |
| token_output_medi | 5375 |
| richieste_medie | 6.9 |
| chiamate_tool_medie | 8.7 |
| lavoro_p50_s | 22.4 |
| lavoro_p95_s | 52.5 |
| attesa_media_s | 0.0 |
| tentativi_provider_medi | 0.0 |
| quota_input_da_cache | 86% |
| costo_medio_usd | 0.0049 $ |
| costo_giudice_medio_usd | 0.0053 $ |

## Esecuzioni

- `senza`: 12 chiuse (0 fallite per l'agente), 0 errori di infrastruttura registrati, 0 senza verdetto del giudice, rifiuti del validatore {'fonti_non_viste': 4, 'numeri_senza_fonti': 2}

Note: le metriche sulla risposta si calcolano sulle esecuzioni completate; Task Success Rate, Guardrail Intervention Rate ed efficienza contano anche quelle fallite per l'agente. Pause e tentativi falliti del provider (429/5xx, rete) sono esclusi dal tempo di lavoro e inclusi nell'attesa media.
