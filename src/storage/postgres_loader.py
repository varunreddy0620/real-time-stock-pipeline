"""Load cleaned bars and indicators into PostgreSQL."""

from __future__ import annotations

import pandas as pd
from sqlalchemy import create_engine, text

from src.config import get_settings
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

UPSERT_RAW = """
INSERT INTO raw_ohlcv (timestamp, ticker, open, high, low, close, volume, ingested_at, source)
VALUES (:timestamp, :ticker, :open, :high, :low, :close, :volume, :ingested_at, :source)
ON CONFLICT (ticker, timestamp) DO UPDATE SET
    open = EXCLUDED.open,
    high = EXCLUDED.high,
    low = EXCLUDED.low,
    close = EXCLUDED.close,
    volume = EXCLUDED.volume,
    ingested_at = EXCLUDED.ingested_at,
    source = EXCLUDED.source
"""

UPSERT_INDICATORS = """
INSERT INTO processed_indicators (
    timestamp, ticker, close, sma_20, sma_50, rsi_14,
    macd, macd_signal, macd_hist, bb_mid, bb_upper, bb_lower, sma_cross
)
VALUES (
    :timestamp, :ticker, :close, :sma_20, :sma_50, :rsi_14,
    :macd, :macd_signal, :macd_hist, :bb_mid, :bb_upper, :bb_lower, :sma_cross
)
ON CONFLICT (ticker, timestamp) DO UPDATE SET
    close = EXCLUDED.close,
    sma_20 = EXCLUDED.sma_20,
    sma_50 = EXCLUDED.sma_50,
    rsi_14 = EXCLUDED.rsi_14,
    macd = EXCLUDED.macd,
    macd_signal = EXCLUDED.macd_signal,
    macd_hist = EXCLUDED.macd_hist,
    bb_mid = EXCLUDED.bb_mid,
    bb_upper = EXCLUDED.bb_upper,
    bb_lower = EXCLUDED.bb_lower,
    sma_cross = EXCLUDED.sma_cross
"""


def get_engine():
    return create_engine(get_settings().postgres_dsn, pool_pre_ping=True)


def upsert_raw(bar: dict) -> None:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(UPSERT_RAW), bar)
    logger.info("Upserted raw bar", extra={"ticker": bar["ticker"]})


def upsert_indicators(row: dict) -> None:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(UPSERT_INDICATORS), row)
    logger.info("Upserted indicators", extra={"ticker": row["ticker"]})


def load_recent_bars(ticker: str, limit: int = 100, up_to_timestamp: str | None = None) -> pd.DataFrame:
    time_filter = "AND timestamp <= :up_to_timestamp" if up_to_timestamp is not None else ""
    query = text(
        f"""
        SELECT timestamp, ticker, open, high, low, close, volume, ingested_at, source
        FROM raw_ohlcv
        WHERE ticker = :ticker
        {time_filter}
        ORDER BY timestamp DESC
        LIMIT :limit
        """
    )

    engine = get_engine()
    with engine.connect() as conn:
        params = {"ticker": ticker, "limit": limit}
        if up_to_timestamp is not None:
            params["up_to_timestamp"] = up_to_timestamp
        frame = pd.read_sql(query, conn, params=params)

    return frame.sort_values("timestamp").reset_index(drop=True)
