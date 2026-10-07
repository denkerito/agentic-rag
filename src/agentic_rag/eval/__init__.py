"""Eval harness: esegue le domande di test con l'agente e misura i risultati.

Il ground truth (eval/ground_truth/) è letto SOLO da questo modulo a runtime. L'assistente di sviluppo
ne conosce la struttura, non i valori (vedi AGENTS.md): i test usano ground truth sintetici.
"""
