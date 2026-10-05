-- Schema del data layer. {EMBEDDING_DIM} viene sostituito da init.py (config.EMBEDDING_DIM).
-- Gli ID testuali sono quelli delle fonti (FATT-*, MOV-*, CTR-*, ...): l'agente li cita.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE clienti (
    id                 TEXT PRIMARY KEY,
    denominazione      TEXT NOT NULL,
    partita_iva        TEXT NOT NULL UNIQUE,
    codice_fiscale     TEXT NOT NULL,
    indirizzo          TEXT NOT NULL,
    pec                TEXT,
    sdi                TEXT,
    settore            TEXT NOT NULL,
    peso_fatturato_pct NUMERIC(5,2) NOT NULL CHECK (peso_fatturato_pct BETWEEN 0 AND 100)
);
COMMENT ON TABLE clienti IS 'Clienti dell''azienda (controparti delle fatture attive).';
COMMENT ON COLUMN clienti.peso_fatturato_pct IS 'Quota percentuale dichiarata sul fatturato.';

CREATE TABLE fornitori (
    id             TEXT PRIMARY KEY,
    denominazione  TEXT NOT NULL,
    partita_iva    TEXT NOT NULL UNIQUE,
    codice_fiscale TEXT NOT NULL,
    indirizzo      TEXT NOT NULL,
    pec            TEXT,
    sdi            TEXT,
    categoria      TEXT NOT NULL
);
COMMENT ON TABLE fornitori IS 'Fornitori dell''azienda (controparti delle fatture passive).';

CREATE TABLE piano_dei_conti (
    codice      TEXT PRIMARY KEY,
    descrizione TEXT NOT NULL,
    tipo        TEXT NOT NULL CHECK (tipo IN ('Attivo', 'Passivo', 'Costi', 'Ricavi'))
);
COMMENT ON TABLE piano_dei_conti IS 'Piano dei conti; i conti Costi/Ricavi fungono da categorie di spesa e di ricavo.';

CREATE TABLE documenti (
    doc_id       TEXT PRIMARY KEY,
    tipo         TEXT NOT NULL CHECK (tipo IN
                     ('email', 'contratto', 'lettera', 'verbale', 'preventivo', 'addendum', 'nota_interna')),
    data         DATE NOT NULL,
    titolo       TEXT NOT NULL,
    fornitore_id TEXT REFERENCES fornitori (id),
    cliente_id   TEXT REFERENCES clienti (id),
    file_path    TEXT NOT NULL,
    contenuto    TEXT NOT NULL,
    CHECK (fornitore_id IS NULL OR cliente_id IS NULL)
);
COMMENT ON TABLE documenti IS 'Documenti non strutturati (contratti, email, lettere, verbali). contenuto = corpo markdown.';

CREATE TABLE documenti_chunks (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    doc_id      TEXT NOT NULL REFERENCES documenti (doc_id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    testo       TEXT NOT NULL,
    embedding   vector({EMBEDDING_DIM}),
    UNIQUE (doc_id, chunk_index)
);
CREATE INDEX documenti_chunks_embedding_idx
    ON documenti_chunks USING hnsw (embedding vector_cosine_ops);
COMMENT ON TABLE documenti_chunks IS 'Chunk dei documenti per la ricerca semantica (pgvector, distanza coseno).';

CREATE TABLE contratti (
    id               TEXT PRIMARY KEY,
    tipo             TEXT NOT NULL CHECK (tipo IN ('attivo', 'passivo')),
    cliente_id       TEXT REFERENCES clienti (id),
    fornitore_id     TEXT REFERENCES fornitori (id),
    oggetto          TEXT NOT NULL,
    importo          NUMERIC(14,2) NOT NULL,
    data_inizio      DATE NOT NULL,
    data_fine        DATE NOT NULL,
    rinnovo          BOOLEAN NOT NULL,
    preavviso_giorni INT NOT NULL,
    CHECK (data_fine >= data_inizio),
    CHECK ((tipo = 'attivo' AND cliente_id IS NOT NULL AND fornitore_id IS NULL)
        OR (tipo = 'passivo' AND fornitore_id IS NOT NULL AND cliente_id IS NULL))
);
COMMENT ON TABLE contratti IS 'Contratti attivi (verso clienti) e passivi (verso fornitori); il testo è in documenti con lo stesso id.';

CREATE TABLE fatture (
    id           TEXT PRIMARY KEY,
    tipo         TEXT NOT NULL CHECK (tipo IN ('attiva', 'passiva')),
    numero       TEXT NOT NULL,
    data         DATE NOT NULL,
    cliente_id   TEXT REFERENCES clienti (id),
    fornitore_id TEXT REFERENCES fornitori (id),
    imponibile   NUMERIC(14,2) NOT NULL,
    iva          NUMERIC(14,2) NOT NULL,
    totale       NUMERIC(14,2) NOT NULL,
    scadenza     DATE NOT NULL,
    CHECK (totale = imponibile + iva),
    CHECK ((tipo = 'attiva' AND cliente_id IS NOT NULL AND fornitore_id IS NULL)
        OR (tipo = 'passiva' AND fornitore_id IS NOT NULL AND cliente_id IS NULL))
);
-- Nessun UNIQUE su (controparte, numero): il dataset contiene volutamente un numero fattura duplicato.
CREATE INDEX fatture_data_idx ON fatture (data);
CREATE INDEX fatture_cliente_idx ON fatture (cliente_id);
CREATE INDEX fatture_fornitore_idx ON fatture (fornitore_id);
COMMENT ON TABLE fatture IS 'Fatture attive (cliente_id valorizzato) e passive (fornitore_id valorizzato).';

CREATE TABLE fatture_righe (
    id           TEXT PRIMARY KEY,
    fattura_id   TEXT NOT NULL REFERENCES fatture (id) ON DELETE CASCADE,
    riga_numero  INT NOT NULL,
    descrizione  TEXT NOT NULL,
    conto_codice TEXT NOT NULL REFERENCES piano_dei_conti (codice),
    quantita     NUMERIC(12,2) NOT NULL,
    prezzo       NUMERIC(14,2) NOT NULL,
    imponibile   NUMERIC(14,2) NOT NULL,
    UNIQUE (fattura_id, riga_numero),
    CHECK (quantita * prezzo = imponibile)
);
CREATE INDEX fatture_righe_conto_idx ON fatture_righe (conto_codice);
COMMENT ON COLUMN fatture_righe.conto_codice IS 'Conto del piano dei conti (categoria di costo/ricavo) della riga.';

CREATE TABLE movimenti_bancari (
    id         TEXT PRIMARY KEY,
    data       DATE NOT NULL,
    valuta     DATE NOT NULL,
    importo    NUMERIC(14,2) NOT NULL,
    causale    TEXT NOT NULL,
    saldo      NUMERIC(14,2) NOT NULL,
    fattura_id TEXT REFERENCES fatture (id)
);
CREATE INDEX movimenti_data_idx ON movimenti_bancari (data);
CREATE INDEX movimenti_fattura_idx ON movimenti_bancari (fattura_id);
COMMENT ON COLUMN movimenti_bancari.importo IS 'Positivo = entrata, negativo = uscita.';
COMMENT ON COLUMN movimenti_bancari.fattura_id IS 'Fattura saldata dal movimento; NULL per F24, stipendi, spese bancarie.';

CREATE TABLE scritture_contabili (
    id                  TEXT PRIMARY KEY,
    data                DATE NOT NULL,
    transazione_id      TEXT NOT NULL,
    conto_codice        TEXT NOT NULL REFERENCES piano_dei_conti (codice),
    dare                NUMERIC(14,2) NOT NULL CHECK (dare >= 0),
    avere               NUMERIC(14,2) NOT NULL CHECK (avere >= 0),
    descrizione         TEXT NOT NULL,
    fattura_id          TEXT REFERENCES fatture (id),
    movimento_id        TEXT REFERENCES movimenti_bancari (id),
    riferimento_esterno TEXT,
    CHECK (NOT (dare > 0 AND avere > 0)),
    CHECK (num_nonnulls(fattura_id, movimento_id, riferimento_esterno) = 1)
);
CREATE INDEX scritture_transazione_idx ON scritture_contabili (transazione_id);
CREATE INDEX scritture_conto_idx ON scritture_contabili (conto_codice);
CREATE INDEX scritture_data_idx ON scritture_contabili (data);
COMMENT ON TABLE scritture_contabili IS 'Partita doppia: per ogni transazione_id la somma dare = somma avere.';
COMMENT ON COLUMN scritture_contabili.riferimento_esterno IS 'Riferimento senza tabella (es. PAGA-2025-01 per i cedolini).';

CREATE TABLE scadenzario (
    id                  TEXT PRIMARY KEY,
    data                DATE NOT NULL,
    tipo                TEXT NOT NULL CHECK (tipo IN
                            ('fattura_passiva', 'fattura_attiva', 'fiscale_f24',
                             'contratto_preavviso', 'rinnovo_contrattuale', 'contratto_adeguamento')),
    cliente_id          TEXT REFERENCES clienti (id),
    fornitore_id        TEXT REFERENCES fornitori (id),
    descrizione         TEXT NOT NULL,
    importo             NUMERIC(14,2) NOT NULL,
    stato               TEXT NOT NULL CHECK (stato IN ('evaso', 'in_scadenza')),
    fattura_id          TEXT REFERENCES fatture (id),
    contratto_id        TEXT REFERENCES contratti (id),
    riferimento_esterno TEXT,
    CHECK (cliente_id IS NULL OR fornitore_id IS NULL),
    CHECK (num_nonnulls(fattura_id, contratto_id, riferimento_esterno) = 1)
);
CREATE INDEX scadenzario_data_idx ON scadenzario (data);
COMMENT ON COLUMN scadenzario.riferimento_esterno IS 'Riferimento senza tabella (es. F24-2025-01).';
