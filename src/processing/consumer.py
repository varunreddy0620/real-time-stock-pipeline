"""Redis Streams consumer: validate → raw storage → indicators → Postgres → alerts."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd
import redis
from pydantic import ValidationError

from src.alerts.notifier import maybe_alert
from src.config import get_settings
from src.processing.cleaner import clean_ohlcv, latest_contiguous_segment
from src.processing.indicators import enrich
from src.processing.schema import OHLCVBar
from src.processing.signals import sma_crossover
from src.storage.minio_writer import write_bar
from src.storage.postgres_loader import load_recent_bars, upsert_indicators, upsert_raw
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


def retry_key(stream: str) -> str:
    return f"{stream}:retry-counts"


def ensure_group(client: redis.Redis, stream: str, group: str) -> None:
    try:
        client.xgroup_create(stream, group, id="0", mkstream=True)
        logger.info("Created consumer group", extra={"stream": stream, "group": group})
    except redis.ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


def process_payload(payload: dict) -> None:
    bar = OHLCVBar.model_validate(payload).model_dump()
    bar["timestamp"] = bar["timestamp"].isoformat()
    if bar.get("ingested_at"):
        bar["ingested_at"] = bar["ingested_at"].isoformat()
    else:
        bar["ingested_at"] = datetime.now(timezone.utc).isoformat()

    write_bar(bar)
    upsert_raw(bar)

    frame = load_recent_bars(bar["ticker"], limit=100, up_to_timestamp=bar["timestamp"])
    frame = clean_ohlcv(frame)
    target_timestamp = pd.Timestamp(bar["timestamp"])
    frame = frame[frame["timestamp"] <= target_timestamp]
    frame = latest_contiguous_segment(frame, get_settings().indicator_max_gap_seconds)
    frame = enrich(frame)
    frame = sma_crossover(frame)
    matching_rows = frame[frame["timestamp"] == target_timestamp]
    if matching_rows.empty:
        raise RuntimeError(f"Current bar {bar['ticker']} {bar['timestamp']} missing from history")
    raw_row = matching_rows.iloc[-1].to_dict()
    row = {}
    for key, value in raw_row.items():
        if pd.isna(value):
            row[key] = None
        elif hasattr(value, "item"):
            row[key] = value.item()
        else:
            row[key] = value
    row["timestamp"] = pd.Timestamp(row["timestamp"]).isoformat()
    upsert_indicators(row)
    maybe_alert(row)


def handle_message(
    client: redis.Redis,
    stream: str,
    group: str,
    message_id: str,
    fields: dict,
    max_delivery_attempts: int = 3,
    dead_letter_stream: str = "stock:ohlcv:dead-letter",
) -> None:
    """Process one stream entry, acknowledging only success or invalid input."""
    try:
        payload = json.loads(fields["payload"])
        process_payload(payload)
    except (ValidationError, json.JSONDecodeError, KeyError, TypeError):
        logger.exception("Invalid stream message", extra={"id": message_id})
        client.xack(stream, group, message_id)
        client.hdel(retry_key(stream), message_id)
    except Exception as exc:
        attempts = client.hincrby(retry_key(stream), message_id, 1)
        if attempts >= max_delivery_attempts:
            client.xadd(
                dead_letter_stream,
                {
                    "original_stream": stream,
                    "original_id": message_id,
                    "payload": fields.get("payload", ""),
                    "error": str(exc),
                },
            )
            client.xack(stream, group, message_id)
            client.hdel(retry_key(stream), message_id)
            logger.exception(
                "Consumer failed; message moved to dead-letter stream",
                extra={"id": message_id, "attempts": attempts},
            )
        else:
            logger.exception(
                "Consumer failed; message left pending",
                extra={"id": message_id, "attempts": attempts},
            )
    else:
        client.xack(stream, group, message_id)
        client.hdel(retry_key(stream), message_id)


def recover_pending(
    client: redis.Redis,
    stream: str,
    group: str,
    consumer_name: str,
    pending_idle_ms: int = 60_000,
    max_delivery_attempts: int = 3,
    dead_letter_stream: str = "stock:ohlcv:dead-letter",
) -> None:
    """Claim and retry messages abandoned by a consumer for at least one minute."""
    result = client.xautoclaim(
        stream,
        group,
        consumer_name,
        min_idle_time=pending_idle_ms,
        start_id="0-0",
        count=10,
    )
    entries = result[1]
    if entries:
        logger.info("Recovering pending messages", extra={"count": len(entries)})
    for message_id, fields in entries:
        handle_message(
            client,
            stream,
            group,
            message_id,
            fields,
            max_delivery_attempts,
            dead_letter_stream,
        )


def run_forever() -> None:
    settings = get_settings()
    client = redis.Redis(host=settings.redis_host, port=settings.redis_port, decode_responses=True)
    ensure_group(client, settings.redis_stream, settings.redis_consumer_group)
    logger.info("Consumer started", extra={"stream": settings.redis_stream})

    while True:
        recover_pending(
            client,
            settings.redis_stream,
            settings.redis_consumer_group,
            settings.redis_consumer_name,
            settings.redis_pending_idle_ms,
            settings.redis_max_delivery_attempts,
            settings.redis_dead_letter_stream,
        )
        messages = client.xreadgroup(
            settings.redis_consumer_group,
            settings.redis_consumer_name,
            {settings.redis_stream: ">"},
            count=10,
            block=5000,
        )
        if not messages:
            continue
        for _stream, entries in messages:
            for message_id, fields in entries:
                handle_message(
                    client,
                    settings.redis_stream,
                    settings.redis_consumer_group,
                    message_id,
                    fields,
                    settings.redis_max_delivery_attempts,
                    settings.redis_dead_letter_stream,
                )


if __name__ == "__main__":
    run_forever()
