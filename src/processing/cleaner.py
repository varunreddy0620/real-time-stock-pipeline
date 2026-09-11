"""Cleaning: sort, drop exact duplicates, forward-fill sparse gaps."""

from __future__ import annotations

import pandas as pd


def clean_ohlcv(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True)
    out = out.sort_values(["ticker", "timestamp"])
    out = out.drop_duplicates(subset=["ticker", "timestamp"], keep="last")
    numeric = ["open", "high", "low", "close", "volume"]
    for col in numeric:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    out[numeric] = out.groupby("ticker", group_keys=False)[numeric].apply(lambda g: g.ffill())
    out = out.dropna(subset=["open", "high", "low", "close"])
    return out.reset_index(drop=True)


def latest_contiguous_segment(frame: pd.DataFrame, max_gap_seconds: int) -> pd.DataFrame:
    """Keep only the latest run of bars without an unexpectedly large time gap."""
    if frame.empty:
        return frame.copy()
    out = frame.sort_values("timestamp").reset_index(drop=True)
    gaps = out["timestamp"].diff()
    breaks = gaps[gaps > pd.Timedelta(seconds=max_gap_seconds)].index
    if len(breaks):
        out = out.iloc[breaks[-1]:]
    return out.reset_index(drop=True)
