"""Publish latest OHLCV bars onto a Redis Stream."""

from __future__ import annotations

import json
import time

import pandas as pd
import redis

from src.config import get_settings
from src.ingestion.fetcher import FetchError, fetch_ohlcv, frame_row_to_bar, load_sample
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


def get_redis() -> redis.Redis:
    settings = get_settings()
    return redis.Redis(host=settings.redis_host, port=settings.redis_port, decode_responses=True)


def publish_bar(client: redis.Redis, stream: str, bar: dict, maxlen: int = 1_000_000) -> str:
    message_id = client.xadd(stream, {"payload": json.dumps(bar)}, maxlen=maxlen, approximate=True)
    logger.info(
        "Published bar",
        extra={"stream": stream, "ticker": bar["ticker"], "message_id": message_id},
    )
    return message_id


class SampleReplay:
    """Replay bundled bars once, in timestamp order, independently per ticker."""

    def __init__(self) -> None:
        self._frames = {}
        self._positions = {}

    def next_bar(self, ticker: str) -> dict | None:
        frame = self._frames.get(ticker)
        if frame is None:
            frame = load_sample(ticker)
            self._frames[ticker] = frame
        position = self._positions.get(ticker, 0)
        if position >= len(frame):
            return None
        self._positions[ticker] = position + 1
        return frame_row_to_bar(frame.iloc[position], source="sample")


def get_next_bar(
    ticker: str,
    settings,
    replay: SampleReplay,
    live_retry_after: dict[str, float],
) -> dict | None:
    """Fetch a live bar when allowed, otherwise advance deterministic sample replay."""
    now = time.monotonic()
    should_try_live = settings.data_source in {"auto", "live"}
    should_try_live = should_try_live and now >= live_retry_after.get(ticker, 0)

    if should_try_live:
        try:
            frame = fetch_ohlcv(
                ticker,
                period=settings.lookback_period,
                interval=settings.ohlcv_interval,
            )
            return frame_row_to_bar(frame.iloc[-1], source="live")
        except FetchError:
            if settings.data_source == "live":
                raise
            live_retry_after[ticker] = now + settings.live_retry_cooldown_seconds
            logger.warning(
                "Live source unavailable; entering sample replay cooldown",
                extra={
                    "ticker": ticker,
                    "cooldown_seconds": settings.live_retry_cooldown_seconds,
                },
            )

    if settings.data_source in {"auto", "sample"}:
        return replay.next_bar(ticker)
    return None


def get_next_bars(
    ticker: str,
    settings,
    replay: SampleReplay,
    live_retry_after: dict[str, float],
    after_timestamp: str | None = None,
) -> list[dict]:
    """Return every unseen live bar, or one deterministic sample bar.

    Publishing the full live window on first startup gives the indicators enough
    history to warm up. Later polls only return bars newer than the last one sent.
    """
    now = time.monotonic()
    should_try_live = settings.data_source in {"auto", "live"}
    should_try_live = should_try_live and now >= live_retry_after.get(ticker, 0)

    if should_try_live:
        try:
            frame = fetch_ohlcv(
                ticker,
                period=settings.lookback_period,
                interval=settings.ohlcv_interval,
            ).sort_values("timestamp")
            if after_timestamp is not None:
                cutoff = pd.Timestamp(after_timestamp)
                timestamps = pd.to_datetime(frame["timestamp"], utc=True)
                frame = frame[timestamps > cutoff]
            return [
                frame_row_to_bar(row, source="live")
                for _, row in frame.iterrows()
            ]
        except FetchError:
            if settings.data_source == "live":
                raise
            live_retry_after[ticker] = now + settings.live_retry_cooldown_seconds
            logger.warning(
                "Live source unavailable; entering sample replay cooldown",
                extra={
                    "ticker": ticker,
                    "cooldown_seconds": settings.live_retry_cooldown_seconds,
                },
            )

    if settings.data_source in {"auto", "sample"}:
        bar = replay.next_bar(ticker)
        return [bar] if bar is not None else []
    return []


def run_forever() -> None:
    settings = get_settings()
    client = get_redis()
    logger.info(
        "Producer started",
        extra={"tickers": settings.ticker_list, "interval": settings.poll_interval_seconds},
    )
    last_published_timestamp = {}
    live_retry_after = {}
    replay = SampleReplay()
    while True:
        for ticker in settings.ticker_list:
            try:
                bars = get_next_bars(
                    ticker,
                    settings,
                    replay,
                    live_retry_after,
                    last_published_timestamp.get(ticker),
                )
                for bar in bars:
                    publish_bar(client, settings.redis_stream, bar, settings.redis_stream_maxlen)
                    last_published_timestamp[ticker] = bar["timestamp"]
            except Exception:
                logger.exception("Producer tick failed", extra={"ticker": ticker})
        time.sleep(settings.poll_interval_seconds)


if __name__ == "__main__":
    run_forever()
