"""Lightweight integration checks that do not require Docker."""

from pathlib import Path

import pandas as pd

from src.ingestion.fetcher import load_sample
from src.processing.indicators import enrich


def test_sample_dataset_exists():
    path = Path("data/sample/ohlcv_sample.csv")
    assert path.exists()
    frame = pd.read_csv(path)
    assert {"timestamp", "ticker", "open", "high", "low", "close", "volume"} <= set(frame.columns)
    assert frame["ticker"].nunique() >= 3


def test_sample_enriches():
    frame = load_sample("AAPL")
    enriched = enrich(frame)
    assert "rsi_14" in enriched.columns
    assert enriched["close"].notna().all()
