# Benchmark del recupero: finale

- ground truth: `eval/ground_truth_finale` · domande con documenti attesi: 25 · documenti pertinenti per domanda: 1.2
- classifiche per documento, primi 10; la ricerca usa il testo della domanda

## Metriche (media sulle domande, IC 95% bootstrap)

| Metrica | Semantica | Semantica con soglia (0.3) | Testuale (full-text) |
|---|---|---|---|
| p@1 | 0.84 [0.68, 0.96] | 0.84 [0.68, 0.96] | 0.64 [0.44, 0.80] |
| p@3 | 0.36 [0.31, 0.43] | 0.35 [0.28, 0.41] | 0.28 [0.21, 0.33] |
| p@5 | 0.24 [0.20, 0.30] | 0.23 [0.19, 0.29] | 0.21 [0.17, 0.26] |
| r@1 | 0.76 [0.59, 0.91] | 0.76 [0.59, 0.91] | 0.56 [0.38, 0.74] |
| r@3 | 0.93 [0.83, 1.00] | 0.89 [0.76, 1.00] | 0.74 [0.56, 0.89] |
| r@5 | 0.99 [0.97, 1.00] | 0.95 [0.85, 1.00] | 0.89 [0.76, 1.00] |
| mrr | 0.90 [0.80, 0.98] | 0.89 [0.77, 0.98] | 0.75 [0.60, 0.88] |

## Differenze appaiate (IC 95%)

| Metrica | semantica - testuale | semantica_soglia - testuale |
|---|---|---|
| p@1 | +0.20 [-0.04, +0.40] | +0.20 [-0.04, +0.40] |
| p@3 | +0.08 [+0.01, +0.15] | +0.07 [+0.00, +0.13] |
| p@5 | +0.03 [+0.00, +0.07] | +0.02 [+0.00, +0.06] |
| r@1 | +0.20 [-0.04, +0.40] | +0.20 [-0.04, +0.40] |
| r@3 | +0.19 [+0.02, +0.37] | +0.15 [-0.01, +0.32] |
| r@5 | +0.10 [+0.00, +0.22] | +0.06 [+0.00, +0.16] |
| mrr | +0.15 [+0.00, +0.29] | +0.14 [-0.01, +0.28] |

Note:
- la precision@k ha un massimo pari a pertinenti ÷ k: con 1.2 documenti pertinenti in media, p@5 non può avvicinarsi a 1;
- i pertinenti sono solo i documenti *necessari* del ground truth: un documento utile ma non elencato conta come errore, quindi la precision è sottostimata;
- la ricerca con soglia restituisce solo i passaggi sotto la distanza di pertinenza, come vede l'agente: può restituire meno di k documenti, e i posti vuoti contano come errori;
- misura gli strumenti con il testo della domanda: l'agente riformula le ricerche e ne fa più d'una, quindi questi numeri non sono il risultato delle indagini.
