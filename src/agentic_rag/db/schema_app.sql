-- Schema `app`: storico delle indagini e dei loro eventi (passi). Idempotente.
-- Volutamente fuori da `public`: l'agente (agent_ro) non lo vede e `db.init --reset` non lo cancella.

CREATE SCHEMA IF NOT EXISTS app;

CREATE TABLE IF NOT EXISTS app.indagini (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domanda     TEXT NOT NULL,
    stato       TEXT NOT NULL DEFAULT 'in_coda'
                CHECK (stato IN ('in_coda', 'in_corso', 'completata', 'fallita', 'interrotta')),
    modello     TEXT NOT NULL,
    creata_il   TIMESTAMPTZ NOT NULL DEFAULT now(),
    iniziata_il TIMESTAMPTZ,
    conclusa_il TIMESTAMPTZ,
    risposta    JSONB,
    errore      TEXT,
    utilizzo    JSONB
);
CREATE INDEX IF NOT EXISTS indagini_creata_idx ON app.indagini (creata_il DESC);

CREATE TABLE IF NOT EXISTS app.indagini_eventi (
    indagine_id UUID NOT NULL REFERENCES app.indagini (id) ON DELETE CASCADE,
    seq         INT NOT NULL,
    tipo        TEXT NOT NULL,
    dati        JSONB NOT NULL,
    creato_il   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (indagine_id, seq)
);
