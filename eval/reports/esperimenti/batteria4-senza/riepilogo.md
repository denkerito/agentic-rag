# Esperimento batteria4-senza

- creato: 2026-10-23T11:44:45+02:00 · codice `src` 41248009ea
- ripetizioni: 2 · domande: 12
- giudice: openrouter:anthropic/claude-sonnet-5.5
- costo: 0.2591 $ (agente 0.1325 $, giudice 0.1266 $) su 24 esecuzioni
- variante `senza`: modello openrouter:anthropic/claude-haiku-5.5, semantica False

Esperimento **valido**.

## Metriche (media sulle domande, IC 95% bootstrap)

| Metrica | senza |
|---|---|
| Task Success Rate | 66.7% [41.7, 91.7] · n=24 |
| Answer Accuracy (LLM-as-a-judge) | 91.7% [75.0, 100.0] · n=23 |
|   di cui parziali | 8.3% [0.0, 25.0] · n=23 |
| Source Citation Recall | 89.2% [80.0, 97.5] · n=19 |
| Numeric Exact Match Recall | 90.0% [75.0, 100.0] · n=19 |
| False Acceptance Rate | 0.0% [0.0, 0.0] · n=4 |
| False Abstention Rate | 12.5% [0.0, 37.5] · n=15 |
| Guardrail Intervention Rate | 54.2% [33.3, 75.0] · n=24 |
| Session Evidence Recall | 84.3% [72.2, 96.3] · n=17 |
| pass^3 | n/a · domande=0 |

## Efficienza

| | senza |
|---|---|
| esecuzioni | 24 |
| token_input_medi | 94070 |
| token_output_medi | 5998 |
| richieste_medie | 6.7 |
| chiamate_tool_medie | 10.2 |
| lavoro_p50_s | 29.1 |
| lavoro_p95_s | 52.9 |
| attesa_media_s | 0.0 |
| tentativi_provider_medi | 0.0 |
| quota_input_da_cache | 85% |
| costo_medio_usd | 0.0055 $ |
| costo_giudice_medio_usd | 0.0055 $ |

## Esecuzioni

- `senza`: 24 chiuse (1 fallite per l'agente), 0 errori di infrastruttura registrati, 0 senza verdetto del giudice, rifiuti del validatore {'fonti_non_viste': 7, 'numeri_senza_fonti': 1, 'assenza_non_provata': 11}

Note: le metriche sulla risposta si calcolano sulle esecuzioni completate; Task Success Rate, Guardrail Intervention Rate ed efficienza contano anche quelle fallite per l'agente. Pause e tentativi falliti del provider (429/5xx, rete) sono esclusi dal tempo di lavoro e inclusi nell'attesa media.
