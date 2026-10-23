# Esperimento batteria3-senza

- creato: 2026-10-22T14:25:06+02:00 · codice `src` 8e0004226b
- ripetizioni: 1 · domande: 12
- giudice: openrouter:anthropic/claude-sonnet-5.5
- costo: 0.1119 $ (agente 0.0468 $, giudice 0.0650 $) su 12 esecuzioni
- variante `senza`: modello openrouter:anthropic/claude-haiku-5.5, semantica False

Esperimento **valido**.

## Metriche (media sulle domande, IC 95% bootstrap)

| Metrica | senza |
|---|---|
| Task Success Rate | 50.0% [25.0, 75.0] · n=12 |
| Answer Accuracy (LLM-as-a-judge) | 83.3% [58.3, 100.0] · n=12 |
|   di cui parziali | 8.3% [0.0, 25.0] · n=12 |
| Source Citation Recall | 77.2% [56.0, 93.5] · n=10 |
| Numeric Exact Match Recall | 78.3% [55.0, 100.0] · n=10 |
| False Acceptance Rate | 0.0% [0.0, 0.0] · n=2 |
| False Abstention Rate | 25.0% [0.0, 62.5] · n=8 |
| Guardrail Intervention Rate | 25.0% [0.0, 50.0] · n=12 |
| Session Evidence Recall | 69.4% [46.3, 89.0] · n=9 |
| pass^3 | n/a · domande=0 |

## Efficienza

| | senza |
|---|---|
| esecuzioni | 12 |
| token_input_medi | 65929 |
| token_output_medi | 4062 |
| richieste_medie | 5.8 |
| chiamate_tool_medie | 8.2 |
| lavoro_p50_s | 23.1 |
| lavoro_p95_s | 33.7 |
| attesa_media_s | 0.0 |
| tentativi_provider_medi | 0.0 |
| quota_input_da_cache | 84% |
| costo_medio_usd | 0.0039 $ |
| costo_giudice_medio_usd | 0.0054 $ |

## Esecuzioni

- `senza`: 12 chiuse (0 fallite per l'agente), 0 errori di infrastruttura registrati, 0 senza verdetto del giudice, rifiuti del validatore {'fonti_non_viste': 2, 'numeri_senza_fonti': 1}

Note: le metriche sulla risposta si calcolano sulle esecuzioni completate; Task Success Rate, Guardrail Intervention Rate ed efficienza contano anche quelle fallite per l'agente. Pause e tentativi falliti del provider (429/5xx, rete) sono esclusi dal tempo di lavoro e inclusi nell'attesa media.
