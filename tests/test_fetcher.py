"""Market fetch transformation and fallback tests."""

import pandas as pd

from src.ingestion import fetcher


def test_fetch_ohlcv_normalizes_download(monkeypatch):
    index = pd.DatetimeIndex(["2026-01-01T10:00:00Z"], name="Datetime")
    downloaded = pd.DataFrame(
        {"Open": [10], "High": [11], "Low": [9], "Close": [10.5], "Volume": [100]},
        index=index,
    )
    monkeypatch.setattr(fetcher.yf, "download", lambda *args, **kwargs: downloaded)

    result = fetcher.fetch_ohlcv("aapl")

    assert result.iloc[0]["ticker"] == "AAPL"
    assert result.iloc[0]["close"] == 10.5


def test_fetch_latest_bar_falls_back_to_sample(monkeypatch):
    monkeypatch.setattr(
        fetcher,
        "fetch_ohlcv",
        lambda *args, **kwargs: (_ for _ in ()).throw(fetcher.FetchError("offline")),
    )

    bar = fetcher.fetch_latest_bar("AAPL")

    assert bar["ticker"] == "AAPL"
    assert bar["timestamp"].endswith("+00:00")


def test_load_sample_rejects_unknown_ticker():
    try:
        fetcher.load_sample("NOT-A-TICKER")
    except fetcher.FetchError as exc:
        assert "No sample data" in str(exc)
    else:
        raise AssertionError("Expected FetchError")
