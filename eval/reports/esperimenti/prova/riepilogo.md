# Esperimento prova

- creato: 2026-10-21T17:05:52+02:00 · codice `src` 6beffb2e83
- ripetizioni: 1 · domande: 2
- giudice: openrouter:anthropic/claude-sonnet-5.5
- costo: 0.0532 $ (agente 0.0296 $, giudice 0.0236 $) su 4 esecuzioni
- variante `con`: modello openrouter:anthropic/claude-haiku-5.5, semantica True
- variante `senza`: modello openrouter:anthropic/claude-haiku-5.5, semantica False

Esperimento **valido**.

## Metriche (media sulle domande, IC 95% bootstrap)

| Metrica | con | senza |
|---|---|---|
| Task Success Rate | 50.0% [0.0, 100.0] · n=2 | 50.0% [0.0, 100.0] · n=2 |
| Answer Accuracy (LLM-as-a-judge) | 50.0% [0.0, 100.0] · n=2 | 0.0% [0.0, 0.0] · n=2 |
|   di cui parziali | 50.0% [0.0, 100.0] · n=2 | 100.0% [100.0, 100.0] · n=2 |
| Source Citation Recall | 25.0% [0.0, 50.0] · n=2 | 25.0% [0.0, 50.0] · n=2 |
| Numeric Exact Match Recall | 66.7% [66.7, 66.7] · n=1 | 66.7% [66.7, 66.7] · n=1 |
| False Acceptance Rate | 0.0% [0.0, 0.0] · n=1 | 0.0% [0.0, 0.0] · n=1 |
| False Abstention Rate | 0.0% [0.0, 0.0] · n=1 | 0.0% [0.0, 0.0] · n=1 |
| Guardrail Intervention Rate | 50.0% [0.0, 100.0] · n=2 | 50.0% [0.0, 100.0] · n=2 |
| Session Evidence Recall | 25.0% [25.0, 25.0] · n=1 | 25.0% [25.0, 25.0] · n=1 |
| pass^3 | n/a · domande=0 | n/a · domande=0 |

## Efficienza

| | con | senza |
|---|---|---|
| esecuzioni | 2 | 2 |
| token_input_medi | 117086 | 94434 |
| token_output_medi | 11626 | 6182 |
| richieste_medie | 8.5 | 8.0 |
| chiamate_tool_medie | 12.5 | 10.0 |
| lavoro_p50_s | 55.5 | 34.2 |
| lavoro_p95_s | 76.7 | 39.4 |
| attesa_media_s | 0.0 | 0.0 |
| tentativi_provider_medi | 0.0 | 0.0 |
| quota_input_da_cache | 84% | 85% |
| costo_medio_usd | 0.0092 $ | 0.0056 $ |
| costo_giudice_medio_usd | 0.0061 $ | 0.0057 $ |

## Esecuzioni

- `con`: 2 chiuse (0 fallite per l'agente), 0 errori di infrastruttura registrati, 0 senza verdetto del giudice, rifiuti del validatore {'fonti_non_viste': 2, 'numeri_senza_fonti': 1}
- `senza`: 2 chiuse (0 fallite per l'agente), 0 errori di infrastruttura registrati, 0 senza verdetto del giudice, rifiuti del validatore {'fonti_non_viste': 1}

## Confronti appaiati (differenza in punti, IC 95%)

| Metrica | senza - con |
|---|---|
| Task Success Rate | +0.0 [+0.0, +0.0] |
| Answer Accuracy (LLM-as-a-judge) | -50.0 [-100.0, +0.0] |
|   di cui parziali | +50.0 [+0.0, +100.0] |
| Source Citation Recall | +0.0 [+0.0, +0.0] |
| Numeric Exact Match Recall | +0.0 [+0.0, +0.0] |
| False Acceptance Rate | +0.0 [+0.0, +0.0] |
| False Abstention Rate | +0.0 [+0.0, +0.0] |
| Guardrail Intervention Rate | +0.0 [+0.0, +0.0] |
| Session Evidence Recall | +0.0 [+0.0, +0.0] |

Note: le metriche sulla risposta si calcolano sulle esecuzioni completate; Task Success Rate, Guardrail Intervention Rate ed efficienza contano anche quelle fallite per l'agente. Pause e tentativi falliti del provider (429/5xx, rete) sono esclusi dal tempo di lavoro e inclusi nell'attesa media.
