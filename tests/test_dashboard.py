"""Dashboard data-loading and chart tests."""

from contextlib import contextmanager

import pandas as pd

from src.dashboard import app
from src.processing.indicators import enrich


class Engine:
    @contextmanager
    def connect(self):
        yield object()


def test_load_bars_marks_postgres_source(monkeypatch):
    frame = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2026-01-02", "2026-01-01"], utc=True),
            "ticker": ["AAPL", "AAPL"],
            "open": [2, 1],
            "high": [3, 2],
            "low": [1, 0.5],
            "close": [2.5, 1.5],
            "volume": [20, 10],
        }
    )
    monkeypatch.setattr(app, "engine", lambda: Engine())
    monkeypatch.setattr(pd, "read_sql", lambda *args, **kwargs: frame)

    result = app.load_bars("AAPL")

    assert result.attrs["source"] == "postgres"
    assert result.iloc[0]["close"] == 1.5


def test_load_bars_falls_back_to_requested_sample(monkeypatch):
    class BrokenEngine:
        @contextmanager
        def connect(self):
            raise RuntimeError("offline")
            yield

    sample = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2026-01-01", "2026-01-01"], utc=True),
            "ticker": ["AAPL", "MSFT"],
            "open": [1, 2],
            "high": [2, 3],
            "low": [0.5, 1],
            "close": [1.5, 2.5],
            "volume": [10, 20],
        }
    )
    monkeypatch.setattr(app, "engine", lambda: BrokenEngine())
    monkeypatch.setattr(pd, "read_csv", lambda *args, **kwargs: sample)

    result = app.load_bars("MSFT")

    assert result.attrs["source"] == "sample"
    assert set(result["ticker"]) == {"MSFT"}


def test_candlestick_contains_price_smas_and_volume():
    frame = pd.read_csv("data/sample/ohlcv_sample.csv", parse_dates=["timestamp"])
    frame = enrich(frame[frame["ticker"] == "AAPL"].reset_index(drop=True))

    figure = app.candlestick(frame, "AAPL")

    assert len(figure.data) == 4


def test_chart_supports_line_bollinger_and_levels():
    frame = pd.read_csv("data/sample/ohlcv_sample.csv", parse_dates=["timestamp"])
    frame = enrich(frame[frame["ticker"] == "AAPL"].reset_index(drop=True))

    figure = app.candlestick(
        frame,
        "AAPL",
        chart_type="Line",
        overlays=("Bollinger Bands", "Support / resistance"),
    )

    assert [trace.name for trace in figure.data] == [
        "Close price",
        "Bollinger upper",
        "Bollinger lower",
        "Volume",
    ]
    assert len(figure.layout.shapes) == 2


def test_analyze_trend_returns_levels_and_momentum():
    frame = pd.read_csv("data/sample/ohlcv_sample.csv", parse_dates=["timestamp"])
    frame = enrich(frame[frame["ticker"] == "AAPL"].reset_index(drop=True))

    result = app.analyze_trend(frame)

    assert result["direction"] in {"Bullish", "Bearish", "Mixed"}
    assert result["momentum"] in {
        "Overbought",
        "Oversold",
        "Positive",
        "Negative",
        "Neutral",
    }
    assert result["support"] < result["resistance"]
