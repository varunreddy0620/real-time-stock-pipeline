"""Parquet writer to MinIO (S3-compatible). Partitioned by ticker/date."""

from __future__ import annotations

import io
from datetime import datetime

import pandas as pd
from minio import Minio

from src.config import get_settings
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


def get_client() -> Minio:
    settings = get_settings()
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


def write_bar(bar: dict) -> str:
    settings = get_settings()
    client = get_client()
    ts = datetime.fromisoformat(bar["timestamp"].replace("Z", "+00:00"))
    ingested_at = datetime.fromisoformat(bar["ingested_at"].replace("Z", "+00:00"))
    date_part = ts.date().isoformat()
    object_name = (
        f"ticker={bar['ticker']}/date={date_part}/"
        f"bar={ts.strftime('%H%M%S%f')}_ingested={ingested_at.strftime('%Y%m%dT%H%M%S%fZ')}.parquet"
    )
    frame = pd.DataFrame([bar])
    buffer = io.BytesIO()
    frame.to_parquet(buffer, index=False)
    payload = buffer.getvalue()
    client.put_object(
        settings.minio_bucket,
        object_name,
        io.BytesIO(payload),
        length=len(payload),
        content_type="application/octet-stream",
    )
    logger.info("Wrote parquet", extra={"object": object_name, "ticker": bar["ticker"]})
    return object_name
