"""SMA crossover signals used by the alerting layer."""

from __future__ import annotations

import pandas as pd


def sma_crossover(frame: pd.DataFrame, fast: str = "sma_20", slow: str = "sma_50") -> pd.DataFrame:
    """Set sma_cross = 1 (bullish) or -1 (bearish) when the fast SMA crosses the slow SMA."""
    out = frame.copy()
    if fast not in out.columns or slow not in out.columns:
        out["sma_cross"] = 0
        return out
    prev_fast = out[fast].shift(1)
    prev_slow = out[slow].shift(1)
    bullish = (prev_fast <= prev_slow) & (out[fast] > out[slow])
    bearish = (prev_fast >= prev_slow) & (out[fast] < out[slow])
    out["sma_cross"] = 0
    out.loc[bullish, "sma_cross"] = 1
    out.loc[bearish, "sma_cross"] = -1
    return out
