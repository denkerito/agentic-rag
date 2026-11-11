# Benchmark del recupero: sviluppo

- ground truth: `eval/ground_truth` · domande con documenti attesi: 9 · documenti pertinenti per domanda: 2.6
- classifiche per documento, primi 10; la ricerca usa il testo della domanda

## Metriche (media sulle domande, IC 95% bootstrap)

| Metrica | Semantica | Semantica con soglia (0.3) | Testuale (full-text) |
|---|---|---|---|
| p@1 | 0.78 [0.44, 1.00] | 0.67 [0.33, 0.89] | 0.89 [0.67, 1.00] |
| p@3 | 0.52 [0.37, 0.67] | 0.44 [0.22, 0.67] | 0.48 [0.30, 0.67] |
| p@5 | 0.38 [0.31, 0.44] | 0.29 [0.16, 0.42] | 0.40 [0.29, 0.53] |
| r@1 | 0.37 [0.20, 0.56] | 0.33 [0.15, 0.54] | 0.40 [0.25, 0.57] |
| r@3 | 0.68 [0.47, 0.87] | 0.61 [0.33, 0.85] | 0.58 [0.39, 0.78] |
| r@5 | 0.80 [0.63, 0.94] | 0.67 [0.37, 0.93] | 0.81 [0.63, 0.96] |
| mrr | 0.85 [0.63, 1.00] | 0.70 [0.41, 0.93] | 0.92 [0.75, 1.00] |

## Differenze appaiate (IC 95%)

| Metrica | semantica - testuale | semantica_soglia - testuale |
|---|---|---|
| p@1 | -0.11 [-0.44, +0.22] | -0.22 [-0.67, +0.22] |
| p@3 | +0.04 [-0.22, +0.30] | -0.04 [-0.37, +0.26] |
| p@5 | -0.02 [-0.13, +0.07] | -0.11 [-0.31, +0.04] |
| r@1 | -0.03 [-0.19, +0.14] | -0.06 [-0.24, +0.11] |
| r@3 | +0.09 [-0.20, +0.41] | +0.03 [-0.31, +0.37] |
| r@5 | -0.02 [-0.17, +0.11] | -0.15 [-0.41, +0.07] |
| mrr | -0.06 [-0.30, +0.18] | -0.21 [-0.56, +0.14] |

Note:
- la precision@k ha un massimo pari a pertinenti ÷ k: con 2.6 documenti pertinenti in media, p@5 non può avvicinarsi a 1;
- i pertinenti sono solo i documenti *necessari* del ground truth: un documento utile ma non elencato conta come errore, quindi la precision è sottostimata;
- la ricerca con soglia restituisce solo i passaggi sotto la distanza di pertinenza, come vede l'agente: può restituire meno di k documenti, e i posti vuoti contano come errori;
- misura gli strumenti con il testo della domanda: l'agente riformula le ricerche e ne fa più d'una, quindi questi numeri non sono il risultato delle indagini.
