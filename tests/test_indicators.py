"""Unit tests for technical indicators."""

import numpy as np
import pandas as pd
import pytest

from src.processing.indicators import bollinger_bands, macd, rsi, sma


def test_sma_constant_series():
    series = pd.Series([10.0] * 30)
    result = sma(series, 20)
    assert result.iloc[19] == pytest.approx(10.0)
    assert np.isnan(result.iloc[18])


def test_sma_rejects_bad_window():
    with pytest.raises(ValueError):
        sma(pd.Series([1, 2, 3]), 0)


def test_rsi_bounds():
    series = pd.Series(np.linspace(100, 140, 40))
    values = rsi(series, 14).dropna()
    assert (values >= 0).all() and (values <= 100).all()
    assert values.iloc[-1] > 50


def test_macd_columns():
    series = pd.Series(np.sin(np.linspace(0, 8, 60)) + 100)
    frame = macd(series)
    assert set(frame.columns) == {"macd", "macd_signal", "macd_hist"}
    assert len(frame) == 60


def test_bollinger_width():
    series = pd.Series(np.random.default_rng(0).normal(100, 2, 40))
    bands = bollinger_bands(series, 20, 2)
    valid = bands.dropna()
    assert (valid["bb_upper"] >= valid["bb_mid"]).all()
    assert (valid["bb_lower"] <= valid["bb_mid"]).all()
