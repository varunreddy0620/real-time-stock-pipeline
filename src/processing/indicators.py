"""Technical indicators implemented from first principles (educational)."""

from __future__ import annotations

import pandas as pd


def sma(series: pd.Series, window: int = 20) -> pd.Series:
    if window <= 0:
        raise ValueError("window must be positive")
    return series.rolling(window=window, min_periods=window).mean()


def rsi(series: pd.Series, window: int = 14) -> pd.Series:
    if window <= 0:
        raise ValueError("window must be positive")

    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(
        alpha=1 / window,
        min_periods=window,
        adjust=False,
    ).mean()
    avg_loss = loss.ewm(
        alpha=1 / window,
        min_periods=window,
        adjust=False,
    ).mean()

    rs = avg_gain / avg_loss
    result = 100 - (100 / (1 + rs))

    result = result.mask((avg_loss == 0) & (avg_gain > 0), 100)
    result = result.mask((avg_gain == 0) & (avg_loss > 0), 0)
    result = result.mask((avg_gain == 0) & (avg_loss == 0), 50)

    return result


def macd(
    series: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return pd.DataFrame({"macd": macd_line, "macd_signal": signal_line, "macd_hist": histogram})


def bollinger_bands(series: pd.Series, window: int = 20, num_std: float = 2.0) -> pd.DataFrame:
    mid = sma(series, window)
    std = series.rolling(window=window, min_periods=window).std()
    return pd.DataFrame(
        {
            "bb_mid": mid,
            "bb_upper": mid + num_std * std,
            "bb_lower": mid - num_std * std,
        }
    )


def enrich(frame: pd.DataFrame, close_col: str = "close") -> pd.DataFrame:
    """Add SMA, RSI, MACD, and Bollinger columns to an OHLCV frame."""
    out = frame.copy()
    close = out[close_col]
    out["sma_20"] = sma(close, 20)
    out["sma_50"] = sma(close, 50)
    out["rsi_14"] = rsi(close, 14)
    out = pd.concat([out, macd(close), bollinger_bands(close)], axis=1)
    return out
