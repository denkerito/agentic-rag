-- Viste economiche: unica definizione di ricavi, costi e margine (per competenza).
-- Idempotente: si applica anche da sola (init --views-only) senza toccare dati ed embedding.
-- Una colonna nuova va aggiunta in fondo: CREATE OR REPLACE VIEW non ne cambia l'ordine.
-- Fonte: scritture_contabili sui conti Costi/Ricavi del piano dei conti, alla data della scrittura.
-- Le righe fattura non bastano: stipendi, oneri INPS e commissioni bancarie esistono solo nelle scritture.
CREATE OR REPLACE VIEW v_economico AS
SELECT s.id AS scrittura_id,
       s.data,
       date_trunc('month', s.data)::date AS mese,
       s.conto_codice,
       p.descrizione AS conto_descrizione,
       p.tipo,
       CASE p.tipo WHEN 'Ricavi' THEN s.avere - s.dare ELSE s.dare - s.avere END AS importo,
       s.fattura_id,
       s.movimento_id,
       s.riferimento_esterno,
       COALESCE(f.cliente_id, f.fornitore_id) AS controparte_id,
       COALESCE(c.denominazione, fo.denominazione) AS controparte,
       s.descrizione
FROM scritture_contabili s
JOIN piano_dei_conti p ON p.codice = s.conto_codice AND p.tipo IN ('Costi', 'Ricavi')
LEFT JOIN fatture f ON f.id = s.fattura_id
LEFT JOIN clienti c ON c.id = f.cliente_id
LEFT JOIN fornitori fo ON fo.id = f.fornitore_id;
COMMENT ON VIEW v_economico IS 'Dettaglio economico per scrittura (competenza). importo: Ricavi = avere-dare, Costi = dare-avere, sempre positivo se normale. Stipendi/oneri/commissioni hanno movimento_id o riferimento_esterno e nessuna controparte.';

CREATE OR REPLACE VIEW v_economico_mensile AS
SELECT mese, conto_codice, conto_descrizione, tipo,
       SUM(importo) AS importo,
       COUNT(*) AS n_scritture,
       array_agg(DISTINCT COALESCE(fattura_id, movimento_id, riferimento_esterno)) AS fonti
FROM v_economico
GROUP BY mese, conto_codice, conto_descrizione, tipo;
COMMENT ON VIEW v_economico_mensile IS 'Importo economico per mese e conto. fonti = ID (FATT-*, MOV-*, ...) a supporto, da citare.';

CREATE OR REPLACE VIEW v_margine_mensile AS
SELECT mese,
       COALESCE(SUM(importo) FILTER (WHERE tipo = 'Ricavi'), 0) AS ricavi,
       COALESCE(SUM(importo) FILTER (WHERE tipo = 'Costi'), 0) AS costi,
       COALESCE(SUM(importo) FILTER (WHERE tipo = 'Ricavi'), 0)
         - COALESCE(SUM(importo) FILTER (WHERE tipo = 'Costi'), 0) AS margine,
       array_agg(DISTINCT COALESCE(fattura_id, movimento_id, riferimento_esterno)) AS fonti
FROM v_economico
GROUP BY mese;
COMMENT ON VIEW v_margine_mensile IS 'Ricavi, costi e margine (ricavi - costi) per mese, per competenza. fonti = ID (FATT-*, MOV-*, ...) a supporto, da citare. Per il dettaglio usare v_economico_mensile / v_economico.';
