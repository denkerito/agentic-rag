-- Valori ammessi delle colonne enumerate, mostrati all'agente nel prompt (schema_prompt.py).
-- Idempotente: si applica anche da solo (init --comments-only) senza toccare dati ed embedding.
-- Se cambia un CHECK ... IN (...) di schema.sql, aggiornare anche il commento qui sotto
-- (lo verifica tests/test_agent_integration.py).

COMMENT ON COLUMN piano_dei_conti.tipo IS 'Valori ammessi (esatti): ''Attivo'', ''Passivo'', ''Costi'', ''Ricavi''.';
COMMENT ON COLUMN documenti.tipo IS 'Valori ammessi (esatti): ''email'', ''contratto'', ''lettera'', ''verbale'', ''preventivo'', ''addendum'', ''nota_interna''.';
COMMENT ON COLUMN contratti.tipo IS 'Valori ammessi (esatti): ''attivo'' (verso clienti), ''passivo'' (verso fornitori).';
COMMENT ON COLUMN fatture.tipo IS 'Valori ammessi (esatti): ''attiva'' (cliente_id valorizzato), ''passiva'' (fornitore_id valorizzato).';
COMMENT ON COLUMN scadenzario.tipo IS 'Valori ammessi (esatti): ''fattura_passiva'', ''fattura_attiva'', ''fiscale_f24'', ''contratto_preavviso'', ''rinnovo_contrattuale'', ''contratto_adeguamento''.';
COMMENT ON COLUMN scadenzario.stato IS 'Valori ammessi (esatti): ''evaso'', ''in_scadenza''.';

COMMENT ON COLUMN v_economico.tipo IS 'Valori ammessi (esatti, plurale e maiuscola iniziale): ''Costi'', ''Ricavi''.';
COMMENT ON COLUMN v_economico_mensile.tipo IS 'Valori ammessi (esatti, plurale e maiuscola iniziale): ''Costi'', ''Ricavi''.';
