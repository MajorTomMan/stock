MIGRATIONS = [
    (
        1,
        "market_data_v1",
        r'''
CREATE TABLE IF NOT EXISTS schema_migration (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS instrument (
    id BIGSERIAL PRIMARY KEY,
    exchange VARCHAR(16) NOT NULL,
    symbol VARCHAR(16) NOT NULL,
    current_name VARCHAR(128),
    full_name VARCHAR(256),
    english_name VARCHAR(256),
    security_type VARCHAR(32) NOT NULL DEFAULT 'STOCK',
    board VARCHAR(64),
    list_date DATE,
    delist_date DATE,
    status VARCHAR(32) NOT NULL DEFAULT 'UNKNOWN',
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    registered_address TEXT,
    region VARCHAR(128),
    province VARCHAR(128),
    city VARCHAR(128),
    industry VARCHAR(128),
    website TEXT,
    source VARCHAR(32),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (exchange, symbol)
);
CREATE INDEX IF NOT EXISTS idx_instrument_status ON instrument(exchange, status);

CREATE TABLE IF NOT EXISTS instrument_name_history (
    id BIGSERIAL PRIMARY KEY,
    instrument_id BIGINT NOT NULL REFERENCES instrument(id) ON DELETE CASCADE,
    effective_date DATE NOT NULL,
    before_name VARCHAR(128),
    after_name VARCHAR(128),
    source VARCHAR(32) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (instrument_id, effective_date, before_name, after_name, source)
);
CREATE INDEX IF NOT EXISTS idx_name_history_instrument_date ON instrument_name_history(instrument_id, effective_date);

CREATE TABLE IF NOT EXISTS trade_calendar (
    exchange VARCHAR(16) NOT NULL,
    trade_date DATE NOT NULL,
    is_open BOOLEAN NOT NULL,
    source VARCHAR(32) NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (exchange, trade_date)
);

CREATE TABLE IF NOT EXISTS ingestion_run (
    id BIGSERIAL PRIMARY KEY,
    provider VARCHAR(32) NOT NULL,
    dataset VARCHAR(64) NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'RUNNING',
    requested_from DATE,
    requested_to DATE,
    row_count BIGINT NOT NULL DEFAULT 0,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_ingestion_run_dataset_started ON ingestion_run(provider, dataset, started_at DESC);

CREATE TABLE IF NOT EXISTS raw_artifact (
    id BIGSERIAL PRIMARY KEY,
    ingestion_run_id BIGINT REFERENCES ingestion_run(id) ON DELETE SET NULL,
    provider VARCHAR(32) NOT NULL,
    dataset VARCHAR(64) NOT NULL,
    business_date DATE,
    file_path TEXT NOT NULL,
    sha256 CHAR(64) NOT NULL,
    byte_size BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (provider, dataset, sha256)
);

CREATE TABLE IF NOT EXISTS market_daily_observation (
    instrument_id BIGINT NOT NULL REFERENCES instrument(id) ON DELETE CASCADE,
    trade_date DATE NOT NULL,
    source VARCHAR(32) NOT NULL,
    source_priority SMALLINT NOT NULL,
    pre_close NUMERIC(20, 6),
    open NUMERIC(20, 6),
    high NUMERIC(20, 6),
    low NUMERIC(20, 6),
    close NUMERIC(20, 6),
    volume_shares BIGINT,
    turnover_cny NUMERIC(24, 2),
    pct_change NUMERIC(12, 6),
    pe_ratio NUMERIC(20, 6),
    trade_status SMALLINT,
    is_st BOOLEAN,
    raw_artifact_id BIGINT REFERENCES raw_artifact(id) ON DELETE SET NULL,
    extra JSONB NOT NULL DEFAULT '{}'::jsonb,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (instrument_id, trade_date, source)
);
CREATE INDEX IF NOT EXISTS idx_daily_observation_date ON market_daily_observation(trade_date, source);

CREATE TABLE IF NOT EXISTS market_daily (
    instrument_id BIGINT NOT NULL REFERENCES instrument(id) ON DELETE CASCADE,
    trade_date DATE NOT NULL,
    pre_close NUMERIC(20, 6),
    open NUMERIC(20, 6),
    high NUMERIC(20, 6),
    low NUMERIC(20, 6),
    close NUMERIC(20, 6),
    volume_shares BIGINT,
    turnover_cny NUMERIC(24, 2),
    pct_change NUMERIC(12, 6),
    pe_ratio NUMERIC(20, 6),
    trade_status SMALLINT,
    is_st BOOLEAN,
    selected_source VARCHAR(32) NOT NULL,
    source_priority SMALLINT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (instrument_id, trade_date)
);
CREATE INDEX IF NOT EXISTS idx_market_daily_date ON market_daily(trade_date);

CREATE TABLE IF NOT EXISTS data_quality_issue (
    id BIGSERIAL PRIMARY KEY,
    instrument_id BIGINT REFERENCES instrument(id) ON DELETE CASCADE,
    trade_date DATE,
    issue_type VARCHAR(64) NOT NULL,
    severity VARCHAR(16) NOT NULL DEFAULT 'WARN',
    source VARCHAR(32),
    status VARCHAR(16) NOT NULL DEFAULT 'OPEN',
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_dq_issue_open ON data_quality_issue(status, issue_type, detected_at DESC);
''',
    ),
]
