"""Schema and cleaning tests."""

from datetime import datetime, timezone

import pandas as pd
import pytest
from pydantic import ValidationError

from src.processing.cleaner import clean_ohlcv, latest_contiguous_segment
from src.processing.schema import OHLCVBar
from src.processing.signals import sma_crossover


def test_schema_accepts_valid_bar():
    bar = OHLCVBar(
        timestamp=datetime.now(timezone.utc),
        ticker="aapl",
        open=10,
        high=11,
        low=9.5,
        close=10.5,
        volume=1_000,
    )
    assert bar.ticker == "AAPL"


def test_schema_rejects_high_below_low():
    with pytest.raises(ValidationError):
        OHLCVBar(
            timestamp=datetime.now(timezone.utc),
            ticker="MSFT",
            open=10,
            high=9,
            low=9.5,
            close=10,
            volume=1,
        )


def test_cleaner_dedupes_and_sorts():
    frame = pd.DataFrame(
        [
            {
                "timestamp": "2026-01-05T15:00:00Z",
                "ticker": "AAPL",
                "open": 1,
                "high": 2,
                "low": 1,
                "close": 1.5,
                "volume": 10,
            },
            {
                "timestamp": "2026-01-05T14:00:00Z",
                "ticker": "AAPL",
                "open": 1,
                "high": 2,
                "low": 1,
                "close": 1.2,
                "volume": 10,
            },
            {
                "timestamp": "2026-01-05T15:00:00Z",
                "ticker": "AAPL",
                "open": 1,
                "high": 3,
                "low": 1,
                "close": 2.0,
                "volume": 11,
            },
        ]
    )
    cleaned = clean_ohlcv(frame)
    assert len(cleaned) == 2
    assert cleaned.iloc[-1]["close"] == 2.0


def test_sma_crossover_flags():
    frame = pd.DataFrame(
        {
            "sma_20": [1, 1, 3, 4],
            "sma_50": [2, 2, 2, 2],
        }
    )
    out = sma_crossover(frame)
    assert list(out["sma_cross"]) == [0, 0, 1, 0]


def test_latest_contiguous_segment_resets_after_large_gap():
    frame = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                ["2026-01-01T10:00:00Z", "2026-01-01T10:05:00Z", "2026-08-01T10:00:00Z"]
            ),
            "close": [10, 11, 20],
        }
    )

    result = latest_contiguous_segment(frame, max_gap_seconds=86_400)

    assert list(result["close"]) == [20]


@pytest.mark.parametrize(
    "invalid_values",
    [
        {"close": 12},
        {"low": 10.25},
        {"open": -1},
        {"volume": -1},
        {"ticker": "   "},
    ],
)
def test_schema_rejects_invalid_market_data(invalid_values):
    values = {
        "timestamp": datetime.now(timezone.utc),
        "ticker": "AAPL",
        "open": 10,
        "high": 11,
        "low": 9,
        "close": 10.5,
        "volume": 1000,
    }
    values.update(invalid_values)

    with pytest.raises(ValidationError):
        OHLCVBar(**values)


def test_schema_rejects_unknown_source_label():
    with pytest.raises(ValidationError):
        OHLCVBar(
            timestamp=datetime.now(timezone.utc),
            ticker="AAPL",
            open=10,
            high=11,
            low=9,
            close=10.5,
            volume=100,
            source="internet",
        )
