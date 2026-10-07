-- Appliqué automatiquement à chaque démarrage de l'API (rejouable sans risque).
-- Sur une base existante, il ajoute seulement ce qui manque : pas besoin de tout effacer.

CREATE TABLE IF NOT EXISTS measurements (
    id          BIGSERIAL PRIMARY KEY,
    device_id   VARCHAR(100)  NOT NULL,
    temperature NUMERIC(5,2)  NOT NULL,
    gaz         NUMERIC(10,2) NOT NULL,
    presence    BOOLEAN,                                  -- NULL = capteur de présence absent
    simulated   BOOLEAN       NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);
ALTER TABLE measurements ALTER COLUMN presence DROP NOT NULL;
CREATE INDEX IF NOT EXISTS idx_measurements_created_at ON measurements (created_at DESC);

CREATE TABLE IF NOT EXISTS alerts (
    id             BIGSERIAL PRIMARY KEY,
    measurement_id BIGINT REFERENCES measurements(id) ON DELETE SET NULL,
    device_id      VARCHAR(100),
    source         VARCHAR(20) NOT NULL DEFAULT 'manuel',  -- esp | vision | anomalie | manuel
    level          VARCHAR(20) NOT NULL CHECK (level IN ('info', 'warning', 'critical')),
    message        TEXT        NOT NULL,
    simulated      BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- Champs envoyés par l'IA
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS type     VARCHAR(50);   -- intrusion, anomalie_temp...
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS score    NUMERIC(10,4);
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS details  JSONB;
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS snapshot TEXT;          -- chemin de la capture d'image
CREATE INDEX IF NOT EXISTS idx_alerts_created_at ON alerts (created_at DESC);
