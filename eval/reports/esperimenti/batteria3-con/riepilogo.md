# Esperimento batteria3-con

- creato: 2026-10-22T14:31:15+02:00 · codice `src` 8e0004226b
- ripetizioni: 1 · domande: 12
- giudice: openrouter:anthropic/claude-sonnet-5.5
- costo: 0.1110 $ (agente 0.0480 $, giudice 0.0631 $) su 12 esecuzioni
- variante `con`: modello openrouter:anthropic/claude-haiku-5.5, semantica True

Esperimento **valido**.

## Metriche (media sulle domande, IC 95% bootstrap)

| Metrica | con |
|---|---|
| Task Success Rate | 50.0% [25.0, 75.0] · n=12 |
| Answer Accuracy (LLM-as-a-judge) | 91.7% [75.0, 100.0] · n=12 |
|   di cui parziali | 8.3% [0.0, 25.0] · n=12 |
| Source Citation Recall | 83.8% [68.8, 97.5] · n=10 |
| Numeric Exact Match Recall | 95.0% [85.0, 100.0] · n=10 |
| False Acceptance Rate | 0.0% [0.0, 0.0] · n=2 |
| False Abstention Rate | 12.5% [0.0, 37.5] · n=8 |
| Guardrail Intervention Rate | 25.0% [0.0, 50.0] · n=12 |
| Session Evidence Recall | 80.6% [60.2, 100.0] · n=9 |
| pass^3 | n/a · domande=0 |

## Efficienza

| | con |
|---|---|
| esecuzioni | 12 |
| token_input_medi | 64166 |
| token_output_medi | 4287 |
| richieste_medie | 5.5 |
| chiamate_tool_medie | 7.7 |
| lavoro_p50_s | 23.5 |
| lavoro_p95_s | 44.6 |
| attesa_media_s | 0.0 |
| tentativi_provider_medi | 0.0 |
| quota_input_da_cache | 84% |
| costo_medio_usd | 0.0040 $ |
| costo_giudice_medio_usd | 0.0053 $ |

## Esecuzioni

- `con`: 12 chiuse (0 fallite per l'agente), 0 errori di infrastruttura registrati, 0 senza verdetto del giudice, rifiuti del validatore {'fonti_non_viste': 4}

Note: le metriche sulla risposta si calcolano sulle esecuzioni completate; Task Success Rate, Guardrail Intervention Rate ed efficienza contano anche quelle fallite per l'agente. Pause e tentativi falliti del provider (429/5xx, rete) sono esclusi dal tempo di lavoro e inclusi nell'attesa media.
