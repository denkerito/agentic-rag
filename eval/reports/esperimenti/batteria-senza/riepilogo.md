# Esperimento batteria-senza

- creato: 2026-10-22T12:00:43+02:00 · codice `src` b6f7d79293
- ripetizioni: 1 · domande: 12
- giudice: openrouter:anthropic/claude-sonnet-5.5
- costo: 0.1172 $ (agente 0.0520 $, giudice 0.0651 $) su 12 esecuzioni
- variante `senza`: modello openrouter:anthropic/claude-haiku-5.5, semantica False

Esperimento **valido**.

## Metriche (media sulle domande, IC 95% bootstrap)

| Metrica | senza |
|---|---|
| Task Success Rate | 25.0% [8.1, 50.0] · n=12 |
| Answer Accuracy (LLM-as-a-judge) | 75.0% [50.0, 100.0] · n=12 |
|   di cui parziali | 25.0% [0.0, 50.0] · n=12 |
| Source Citation Recall | 70.2% [49.5, 87.7] · n=10 |
| Numeric Exact Match Recall | 76.2% [53.8, 94.4] · n=9 |
| False Acceptance Rate | 0.0% [0.0, 0.0] · n=2 |
| False Abstention Rate | 12.5% [0.0, 37.5] · n=8 |
| Guardrail Intervention Rate | 25.0% [8.3, 50.0] · n=12 |
| Session Evidence Recall | 84.3% [66.7, 100.0] · n=9 |
| pass^3 | n/a · domande=0 |

## Efficienza

| | senza |
|---|---|
| esecuzioni | 12 |
| token_input_medi | 74196 |
| token_output_medi | 4799 |
| richieste_medie | 6.6 |
| chiamate_tool_medie | 8.8 |
| lavoro_p50_s | 19.1 |
| lavoro_p95_s | 48.7 |
| attesa_media_s | 0.0 |
| tentativi_provider_medi | 0.0 |
| quota_input_da_cache | 86% |
| costo_medio_usd | 0.0043 $ |
| costo_giudice_medio_usd | 0.0054 $ |

## Esecuzioni

- `senza`: 12 chiuse (0 fallite per l'agente), 0 errori di infrastruttura registrati, 0 senza verdetto del giudice, rifiuti del validatore {'fonti_non_viste': 4, 'numeri_senza_fonti': 2}

Note: le metriche sulla risposta si calcolano sulle esecuzioni completate; Task Success Rate, Guardrail Intervention Rate ed efficienza contano anche quelle fallite per l'agente. Pause e tentativi falliti del provider (429/5xx, rete) sono esclusi dal tempo di lavoro e inclusi nell'attesa media.
