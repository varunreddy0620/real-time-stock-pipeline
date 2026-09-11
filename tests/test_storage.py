"""Storage adapter tests with external clients replaced by fakes."""

from contextlib import contextmanager
from types import SimpleNamespace

import pandas as pd

from src.storage import minio_writer, postgres_loader


def test_minio_key_preserves_separate_ingestions(monkeypatch):
    names = []

    class Client:
        def put_object(self, bucket, name, payload, **kwargs):
            names.append(name)

    settings = SimpleNamespace(minio_bucket="raw-ohlcv")
    monkeypatch.setattr(minio_writer, "get_settings", lambda: settings)
    monkeypatch.setattr(minio_writer, "get_client", Client)
    base = {
        "timestamp": "2026-01-01T10:00:00+00:00",
        "ticker": "AAPL",
        "open": 10,
        "high": 11,
        "low": 9,
        "close": 10.5,
        "volume": 100,
    }

    minio_writer.write_bar({**base, "ingested_at": "2026-01-01T10:01:00+00:00"})
    minio_writer.write_bar({**base, "ingested_at": "2026-01-01T10:02:00+00:00"})

    assert len(set(names)) == 2
    assert all(name.startswith("ticker=AAPL/date=2026-01-01/") for name in names)


def test_postgres_upserts_execute_expected_statement(monkeypatch):
    calls = []

    class Connection:
        def execute(self, statement, values):
            calls.append((str(statement), values))

    class Engine:
        @contextmanager
        def begin(self):
            yield Connection()

    monkeypatch.setattr(postgres_loader, "get_engine", Engine)
    bar = {"ticker": "AAPL"}

    postgres_loader.upsert_raw(bar)
    postgres_loader.upsert_indicators(bar)

    assert "INSERT INTO raw_ohlcv" in calls[0][0]
    assert "INSERT INTO processed_indicators" in calls[1][0]


def test_load_recent_bars_sorts_oldest_first(monkeypatch):
    class Engine:
        @contextmanager
        def connect(self):
            yield object()

    frame = pd.DataFrame({"timestamp": ["2026-01-02", "2026-01-01"]})
    monkeypatch.setattr(postgres_loader, "get_engine", Engine)
    monkeypatch.setattr(pd, "read_sql", lambda *args, **kwargs: frame)

    result = postgres_loader.load_recent_bars("AAPL")

    assert list(result["timestamp"]) == ["2026-01-01", "2026-01-02"]
