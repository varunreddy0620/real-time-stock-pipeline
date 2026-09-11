"""OHLCV fetcher with retry/backoff. Primary source: yfinance. Fallback: sample CSV."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.utils.logging_config import get_logger

logger = get_logger(__name__)

SAMPLE_PATH = Path(__file__).resolve().parents[2] / "data" / "sample" / "ohlcv_sample.csv"


class FetchError(RuntimeError):
    """Raised when market data cannot be retrieved."""


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type(FetchError),
    reraise=True,
)
def fetch_ohlcv(ticker: str, period: str = "1d", interval: str = "5m") -> pd.DataFrame:
    """Fetch OHLCV bars for a ticker. Retries up to 3 times with exponential backoff."""
    logger.info("Fetching OHLCV", extra={"ticker": ticker, "interval": interval})
    try:
        data = yf.download(
            ticker,
            period=period,
            interval=interval,
            progress=False,
            auto_adjust=True,
            threads=False,
        )
    except Exception as exc:  # noqa: BLE001
        raise FetchError(f"yfinance failed for {ticker}: {exc}") from exc

    if data is None or data.empty:
        raise FetchError(f"No data returned for {ticker}")

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    data = data.rename(columns=str.lower)
    data = data.reset_index()
    time_col = "Datetime" if "Datetime" in data.columns else "Date"
    data = data.rename(columns={time_col: "timestamp"})
    data["ticker"] = ticker.upper()
    data["ingested_at"] = datetime.now(timezone.utc)
    keep = ["timestamp", "ticker", "open", "high", "low", "close", "volume", "ingested_at"]
    return data[keep]


def fetch_latest_bar(ticker: str, period: str = "1d", interval: str = "5m") -> dict:
    """Return the most recent OHLCV bar as a JSON-serializable dict."""
    try:
        frame = fetch_ohlcv(ticker, period=period, interval=interval)
        source = "live"
    except FetchError:
        logger.warning("Falling back to sample data", extra={"ticker": ticker})
        frame = load_sample(ticker)
        source = "sample"

    return frame_row_to_bar(frame.iloc[-1], source=source)


def frame_row_to_bar(row: pd.Series, source: str = "live") -> dict:
    """Convert a frame row into the JSON-safe stream payload shape."""
    return {
        "timestamp": pd.Timestamp(row["timestamp"]).isoformat(),
        "ticker": str(row["ticker"]),
        "open": float(row["open"]),
        "high": float(row["high"]),
        "low": float(row["low"]),
        "close": float(row["close"]),
        "volume": float(row["volume"]),
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
    }


def load_sample(ticker: str) -> pd.DataFrame:
    if not SAMPLE_PATH.exists():
        raise FetchError("Sample dataset missing and live fetch failed")
    frame = pd.read_csv(SAMPLE_PATH, parse_dates=["timestamp"])
    subset = frame[frame["ticker"].str.upper() == ticker.upper()]
    if subset.empty:
        raise FetchError(
            f"No sample data for {ticker.upper()} and live fetch failed. "
            f"Add rows for this ticker to {SAMPLE_PATH} or fix the live fetch."
        )
    return subset.sort_values("timestamp").reset_index(drop=True)
