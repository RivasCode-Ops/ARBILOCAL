-- ARBILOCAL — esquema para parcerias e motor de análise (futuro)
-- SQLite 3.35+ (JSON1). Reaplicável: CREATE … IF NOT EXISTS.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS partner (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    slug          TEXT NOT NULL UNIQUE,
    display_name  TEXT NOT NULL,
    legal_name    TEXT,
    trust_tier    TEXT NOT NULL CHECK (trust_tier IN ('A', 'B', 'C')),
    platform_type TEXT NOT NULL CHECK (platform_type IN ('marketplace', 'distribuidor', 'fabricante', 'outro')),
    verified_at   TEXT,
    active        INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    metadata      TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_partner_trust ON partner (trust_tier, active);

CREATE TABLE IF NOT EXISTS partner_offer (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    partner_id     INTEGER NOT NULL REFERENCES partner (id) ON DELETE CASCADE,
    external_sku   TEXT NOT NULL,
    title_snapshot TEXT,
    category_hint  TEXT,
    last_seen_at   TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (partner_id, external_sku)
);

CREATE INDEX IF NOT EXISTS idx_partner_offer_partner ON partner_offer (partner_id);

CREATE TABLE IF NOT EXISTS analysis_run (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    partner_id         INTEGER REFERENCES partner (id) ON DELETE SET NULL,
    partner_offer_id   INTEGER REFERENCES partner_offer (id) ON DELETE SET NULL,
    query_text         TEXT NOT NULL,
    cost_brl           REAL NOT NULL,
    ml_fee_rate        REAL,
    ml_total_results   INTEGER,
    ml_sample_size     INTEGER,
    report_path        TEXT,
    exit_code          INTEGER,
    preco_medio        REAL,
    lucro              REAL,
    margem             REAL,
    concorrencia       TEXT,
    recomendacao       TEXT,
    motivo             TEXT,
    veredito           TEXT,
    risco              TEXT,
    resultado_final    TEXT,
    generated_at       TEXT,
    ingested_at        TEXT,
    ingest_source      TEXT,
    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (report_path)
);

CREATE INDEX IF NOT EXISTS idx_analysis_run_created ON analysis_run (created_at);
CREATE INDEX IF NOT EXISTS idx_analysis_run_partner ON analysis_run (partner_id);

CREATE TABLE IF NOT EXISTS score_fact (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_run_id  INTEGER NOT NULL REFERENCES analysis_run (id) ON DELETE CASCADE,
    motor            TEXT NOT NULL CHECK (motor IN ('supplier', 'product', 'demand', 'financial')),
    metric_key       TEXT NOT NULL,
    value_0_100      REAL CHECK (value_0_100 IS NULL OR (value_0_100 >= 0 AND value_0_100 <= 100)),
    weight           REAL NOT NULL DEFAULT 1.0,
    source           TEXT NOT NULL CHECK (source IN ('partner_api', 'computed', 'manual', 'ml_proxy')),
    evidence_json    TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (analysis_run_id, motor, metric_key)
);

CREATE INDEX IF NOT EXISTS idx_score_fact_run ON score_fact (analysis_run_id);
CREATE INDEX IF NOT EXISTS idx_score_fact_motor ON score_fact (motor);

CREATE TABLE IF NOT EXISTS score_dimension_aggregate (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_run_id  INTEGER NOT NULL REFERENCES analysis_run (id) ON DELETE CASCADE,
    motor            TEXT NOT NULL CHECK (motor IN ('supplier', 'product', 'demand', 'financial')),
    score_0_100      REAL,
    rationale        TEXT,
    UNIQUE (analysis_run_id, motor)
);

/*
Mapeamento sugerido (metric_key) — preencher via ETL / motor futuro:

1) supplier — tempo_mercado, avaliacoes_media, plataforma_confiavel, tier_parceiro_herdado
2) product — saturacao, diferenciacao, problema_resolve
3) demand — volume_vendas_proxy, interesse_atual, tendencia
4) financial — margem, custo_real_completo, ponto_lucro

Parceiro trust_tier = 'A': score_fact em supplier pode vir de partner_api ou defaults auditáveis.
*/
