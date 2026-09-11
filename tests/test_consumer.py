"""Tests for Redis message acknowledgement and recovery behavior."""

import json

import pandas as pd

from src.processing import consumer


class FakeRedis:
    def __init__(self, claimed=None):
        self.acked = []
        self.claimed = claimed or []
        self.hashes = {}
        self.added = []

    def xack(self, stream, group, message_id):
        self.acked.append((stream, group, message_id))

    def xautoclaim(self, *args, **kwargs):
        return ["0-0", self.claimed, []]

    def hincrby(self, key, field, amount):
        value = self.hashes.get((key, field), 0) + amount
        self.hashes[(key, field)] = value
        return value

    def hdel(self, key, field):
        self.hashes.pop((key, field), None)

    def xadd(self, stream, fields):
        self.added.append((stream, fields))
        return "dead-1"


def test_handle_message_acknowledges_success(monkeypatch):
    client = FakeRedis()
    monkeypatch.setattr(consumer, "process_payload", lambda payload: None)

    consumer.handle_message(
        client,
        "stock:ohlcv",
        "pipeline",
        "1-0",
        {"payload": json.dumps({"ticker": "AAPL"})},
    )

    assert client.acked == [("stock:ohlcv", "pipeline", "1-0")]


def test_handle_message_leaves_transient_failure_pending(monkeypatch):
    client = FakeRedis()

    def fail(_payload):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(consumer, "process_payload", fail)
    consumer.handle_message(
        client,
        "stock:ohlcv",
        "pipeline",
        "2-0",
        {"payload": json.dumps({"ticker": "AAPL"})},
    )

    assert client.acked == []


def test_handle_message_acknowledges_invalid_json():
    client = FakeRedis()

    consumer.handle_message(
        client,
        "stock:ohlcv",
        "pipeline",
        "3-0",
        {"payload": "not-json"},
    )

    assert client.acked == [("stock:ohlcv", "pipeline", "3-0")]


def test_recover_pending_reprocesses_claimed_message(monkeypatch):
    claimed = [("4-0", {"payload": json.dumps({"ticker": "MSFT"})})]
    client = FakeRedis(claimed=claimed)
    monkeypatch.setattr(consumer, "process_payload", lambda payload: None)

    consumer.recover_pending(client, "stock:ohlcv", "pipeline", "worker-1")

    assert client.acked == [("stock:ohlcv", "pipeline", "4-0")]


def test_repeated_failure_moves_message_to_dead_letter(monkeypatch):
    client = FakeRedis()

    def fail(_payload):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(consumer, "process_payload", fail)
    fields = {"payload": json.dumps({"ticker": "AAPL"})}
    for _ in range(3):
        consumer.handle_message(client, "stock:ohlcv", "pipeline", "5-0", fields)

    assert client.acked == [("stock:ohlcv", "pipeline", "5-0")]
    assert client.added[0][0] == "stock:ohlcv:dead-letter"
    assert client.added[0][1]["original_id"] == "5-0"


def test_process_payload_saves_the_messages_own_timestamp(monkeypatch):
    saved = []
    history = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                ["2026-01-01T10:00:00Z", "2026-01-01T10:05:00Z", "2026-01-01T10:10:00Z"]
            ),
            "ticker": ["AAPL"] * 3,
            "open": [10, 11, 12],
            "high": [11, 12, 13],
            "low": [9, 10, 11],
            "close": [10.5, 11.5, 12.5],
            "volume": [100, 110, 120],
            "ingested_at": pd.to_datetime(["2026-01-01T11:00:00Z"] * 3),
        }
    )
    monkeypatch.setattr(consumer, "write_bar", lambda bar: None)
    monkeypatch.setattr(consumer, "upsert_raw", lambda bar: None)
    monkeypatch.setattr(consumer, "load_recent_bars", lambda ticker, limit, up_to_timestamp: history)
    monkeypatch.setattr(consumer, "upsert_indicators", saved.append)
    monkeypatch.setattr(consumer, "maybe_alert", lambda row: None)
    payload = {
        "timestamp": "2026-01-01T10:05:00Z",
        "ticker": "AAPL",
        "open": 11,
        "high": 12,
        "low": 10,
        "close": 11.5,
        "volume": 110,
    }

    consumer.process_payload(payload)

    assert saved[0]["timestamp"] == "2026-01-01T10:05:00+00:00"
