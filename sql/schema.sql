-- Create schema for the educational market pipeline.

CREATE TABLE IF NOT EXISTS raw_ohlcv (
    id              BIGSERIAL PRIMARY KEY,
    timestamp       TIMESTAMPTZ NOT NULL,
    ticker          VARCHAR(16) NOT NULL,
    open            DOUBLE PRECISION NOT NULL,
    high            DOUBLE PRECISION NOT NULL,
    low             DOUBLE PRECISION NOT NULL,
    close           DOUBLE PRECISION NOT NULL,
    volume          DOUBLE PRECISION NOT NULL,
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source          VARCHAR(16) NOT NULL DEFAULT 'unknown',
    CONSTRAINT uq_raw_ohlcv_ticker_ts UNIQUE (ticker, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_raw_ohlcv_ticker_ts ON raw_ohlcv (ticker, timestamp DESC);

CREATE TABLE IF NOT EXISTS processed_indicators (
    id              BIGSERIAL PRIMARY KEY,
    timestamp       TIMESTAMPTZ NOT NULL,
    ticker          VARCHAR(16) NOT NULL,
    close           DOUBLE PRECISION NOT NULL,
    sma_20          DOUBLE PRECISION,
    sma_50          DOUBLE PRECISION,
    rsi_14          DOUBLE PRECISION,
    macd            DOUBLE PRECISION,
    macd_signal     DOUBLE PRECISION,
    macd_hist       DOUBLE PRECISION,
    bb_mid          DOUBLE PRECISION,
    bb_upper        DOUBLE PRECISION,
    bb_lower        DOUBLE PRECISION,
    sma_cross       SMALLINT NOT NULL DEFAULT 0,
    CONSTRAINT uq_indicators_ticker_ts UNIQUE (ticker, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_indicators_ticker_ts ON processed_indicators (ticker, timestamp DESC);
