# Esperimento q9-anteprima-senza

- creato: 2026-10-22T17:42:56+02:00 · codice `src` 43568c00ea
- ripetizioni: 2 · domande: 1
- giudice: openrouter:anthropic/claude-sonnet-5.5
- costo: 0.0208 $ (agente 0.0091 $, giudice 0.0117 $) su 2 esecuzioni
- variante `senza`: modello openrouter:anthropic/claude-haiku-5.5, semantica False

Esperimento **valido**.

## Metriche (media sulle domande, IC 95% bootstrap)

| Metrica | senza |
|---|---|
| Task Success Rate | 100.0% [100.0, 100.0] · n=2 |
| Answer Accuracy (LLM-as-a-judge) | 100.0% [100.0, 100.0] · n=2 |
|   di cui parziali | 0.0% [0.0, 0.0] · n=2 |
| Source Citation Recall | 100.0% [100.0, 100.0] · n=2 |
| Numeric Exact Match Recall | 100.0% [100.0, 100.0] · n=2 |
| False Acceptance Rate | n/a · n=0 |
| False Abstention Rate | 0.0% [0.0, 0.0] · n=2 |
| Guardrail Intervention Rate | 50.0% [50.0, 50.0] · n=2 |
| Session Evidence Recall | 100.0% [100.0, 100.0] · n=2 |
| pass^3 | n/a · domande=0 |

## Efficienza

| | senza |
|---|---|
| esecuzioni | 2 |
| token_input_medi | 68492 |
| token_output_medi | 4980 |
| richieste_medie | 7.0 |
| chiamate_tool_medie | 10.5 |
| lavoro_p50_s | 27.9 |
| lavoro_p95_s | 28.9 |
| attesa_media_s | 0.0 |
| tentativi_provider_medi | 0.0 |
| quota_input_da_cache | 83% |
| costo_medio_usd | 0.0045 $ |
| costo_giudice_medio_usd | 0.0059 $ |

## Esecuzioni

- `senza`: 2 chiuse (0 fallite per l'agente), 0 errori di infrastruttura registrati, 0 senza verdetto del giudice, rifiuti del validatore {'numeri_senza_fonti': 1}

Note: le metriche sulla risposta si calcolano sulle esecuzioni completate; Task Success Rate, Guardrail Intervention Rate ed efficienza contano anche quelle fallite per l'agente. Pause e tentativi falliti del provider (429/5xx, rete) sono esclusi dal tempo di lavoro e inclusi nell'attesa media.
