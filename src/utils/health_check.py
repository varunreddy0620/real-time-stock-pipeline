"""Lightweight health checks used by Docker and the dashboard."""

from __future__ import annotations

from datetime import datetime, timezone

import redis
from minio import Minio
from sqlalchemy import create_engine, text

from src.config import get_settings


def check_redis() -> dict:
    settings = get_settings()
    try:
        client = redis.Redis(host=settings.redis_host, port=settings.redis_port, socket_timeout=2)
        client.ping()
        return {"service": "redis", "ok": True}
    except Exception as exc:  # noqa: BLE001 — health checks must never crash
        return {"service": "redis", "ok": False, "error": str(exc)}


def check_postgres() -> dict:
    settings = get_settings()
    try:
        engine = create_engine(settings.postgres_dsn, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"service": "postgres", "ok": True}
    except Exception as exc:  # noqa: BLE001
        return {"service": "postgres", "ok": False, "error": str(exc)}


def check_minio() -> dict:
    settings = get_settings()
    try:
        client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        ok = client.bucket_exists(settings.minio_bucket)
        result = {"service": "minio", "ok": ok}
        if not ok:
            result["error"] = f"Bucket {settings.minio_bucket!r} does not exist"
        return result
    except Exception as exc:  # noqa: BLE001
        return {"service": "minio", "ok": False, "error": str(exc)}


def overall_health() -> dict:
    checks = [check_redis(), check_postgres(), check_minio()]
    ok = all(c["ok"] for c in checks)
    return {
        "status": "ok" if ok else "degraded",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
    }
