-- Ricerca testuale (full-text italiano) sui documenti: tool `cerca_testo` dell'agente.
-- Idempotente: si applica anche da solo (init --fulltext-only) senza toccare dati ed embedding.
-- Titolo con peso A, contenuto con peso B: a parità di termini pesa di più una corrispondenza nel titolo.

ALTER TABLE documenti ADD COLUMN IF NOT EXISTS tsv tsvector GENERATED ALWAYS AS (
    setweight(to_tsvector('italian', titolo), 'A') || setweight(to_tsvector('italian', contenuto), 'B')
) STORED;
CREATE INDEX IF NOT EXISTS documenti_tsv_idx ON documenti USING gin (tsv);
COMMENT ON COLUMN documenti.tsv IS 'Lessemi (italiano) di titolo e contenuto per la ricerca testuale.';
