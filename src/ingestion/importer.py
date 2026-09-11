"""Validate and stream a user-supplied CSV or Parquet OHLCV dataset through Redis."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import pandas as pd
import pyarrow.parquet as pq
import redis
from pydantic import ValidationError

from src.config import get_settings
from src.processing.schema import OHLCVBar
from src.utils.logging_config import get_logger

logger = get_logger(__name__)
REQUIRED_COLUMNS = ("timestamp", "ticker", "open", "high", "low", "close", "volume")


class DatasetValidationError(ValueError):
    """Raised with row/file context when an import dataset is invalid."""


def iter_frames(path: Path, batch_size: int) -> Iterator[pd.DataFrame]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        yield from pd.read_csv(path, chunksize=batch_size)
        return
    if suffix in {".parquet", ".pq"}:
        parquet_file = pq.ParquetFile(path)
        for batch in parquet_file.iter_batches(batch_size=batch_size):
            yield batch.to_pandas()
        return
    raise DatasetValidationError("Dataset must be a .csv, .parquet, or .pq file")


def normalize_frame(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out.columns = [str(column).strip().lower() for column in out.columns]
    missing = sorted(set(REQUIRED_COLUMNS) - set(out.columns))
    if missing:
        raise DatasetValidationError(f"Missing required columns: {', '.join(missing)}")
    out = out[list(REQUIRED_COLUMNS)]
    out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True, errors="coerce")
    if out["timestamp"].isna().any():
        raise DatasetValidationError("One or more timestamps are invalid")
    return out


def iter_validated_bars(path: Path, batch_size: int = 5_000) -> Iterator[dict]:
    if not path.is_file():
        raise DatasetValidationError(f"Dataset does not exist: {path}")

    last_timestamp_by_ticker = {}
    row_number = 1
    for frame in iter_frames(path, batch_size):
        normalized = normalize_frame(frame)
        for record in normalized.to_dict(orient="records"):
            row_number += 1
            record["source"] = "local"
            record["ingested_at"] = datetime.now(timezone.utc)
            try:
                bar = OHLCVBar.model_validate(record)
            except ValidationError as exc:
                raise DatasetValidationError(f"Invalid data at row {row_number}: {exc}") from exc

            previous = last_timestamp_by_ticker.get(bar.ticker)
            if previous is not None and bar.timestamp < previous:
                raise DatasetValidationError(
                    f"Rows for {bar.ticker} are not sorted by timestamp at row {row_number}"
                )
            last_timestamp_by_ticker[bar.ticker] = bar.timestamp
            yield bar.model_dump(mode="json")


def validate_dataset(path: Path, batch_size: int = 5_000) -> dict:
    count = 0
    tickers = set()
    first_timestamp = None
    last_timestamp = None
    for bar in iter_validated_bars(path, batch_size):
        count += 1
        tickers.add(bar["ticker"])
        timestamp = bar["timestamp"]
        first_timestamp = timestamp if first_timestamp is None else min(first_timestamp, timestamp)
        last_timestamp = timestamp if last_timestamp is None else max(last_timestamp, timestamp)
    if count == 0:
        raise DatasetValidationError("Dataset contains no rows")
    return {
        "rows": count,
        "tickers": sorted(tickers),
        "first_timestamp": first_timestamp,
        "last_timestamp": last_timestamp,
    }


def publish_dataset(
    client: redis.Redis,
    path: Path,
    stream: str,
    stream_maxlen: int,
    batch_size: int = 5_000,
    batch_delay_seconds: float = 0.05,
) -> dict:
    count = 0
    tickers = set()
    pipeline = client.pipeline(transaction=False)
    for bar in iter_validated_bars(path, batch_size):
        pipeline.xadd(
            stream,
            {"payload": json.dumps(bar)},
            maxlen=stream_maxlen,
            approximate=True,
        )
        count += 1
        tickers.add(bar["ticker"])
        if count % batch_size == 0:
            pipeline.execute()
            logger.info("Dataset import progress", extra={"rows_published": count})
            if batch_delay_seconds:
                time.sleep(batch_delay_seconds)
    pipeline.execute()
    return {"rows": count, "tickers": sorted(tickers), "stream": stream}


def wait_until_consumed(
    client: redis.Redis,
    stream: str,
    group: str,
    timeout_seconds: float = 600,
    poll_seconds: float = 1,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        groups = client.xinfo_groups(stream)
        group_info = next((item for item in groups if item["name"] == group), None)
        if group_info is not None:
            lag = group_info.get("lag")
            pending = group_info.get("pending", 0)
            if lag == 0 and pending == 0:
                return
        time.sleep(poll_seconds)
    raise TimeoutError(f"Consumer group {group!r} did not drain within {timeout_seconds} seconds")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", required=True, type=Path, help="CSV or Parquet dataset path")
    parser.add_argument("--batch-size", type=int, default=5_000)
    parser.add_argument("--batch-delay-seconds", type=float, default=0.05)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--no-wait", action="store_true", help="Return before the consumer drains the stream")
    parser.add_argument("--wait-timeout", type=float, default=600)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.batch_size <= 0:
        raise SystemExit("--batch-size must be positive")
    if args.batch_delay_seconds < 0:
        raise SystemExit("--batch-delay-seconds cannot be negative")

    summary = validate_dataset(args.file, args.batch_size)
    print("Dataset valid: " + json.dumps(summary))
    if args.validate_only:
        return

    settings = get_settings()
    client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    client.ping()
    imported = publish_dataset(
        client,
        args.file,
        settings.redis_stream,
        settings.redis_stream_maxlen,
        args.batch_size,
        args.batch_delay_seconds,
    )
    print("Dataset published: " + json.dumps(imported))
    if not args.no_wait:
        wait_until_consumed(
            client,
            settings.redis_stream,
            settings.redis_consumer_group,
            timeout_seconds=args.wait_timeout,
        )
        print("Dataset processing complete")


if __name__ == "__main__":
    main()
