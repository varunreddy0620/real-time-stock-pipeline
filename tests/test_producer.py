"""Producer source-selection and replay tests."""

from types import SimpleNamespace

import pandas as pd
import pytest

from src.ingestion import producer
from src.ingestion.fetcher import FetchError


def settings(data_source="sample"):
    return SimpleNamespace(
        data_source=data_source,
        lookback_period="1d",
        ohlcv_interval="5m",
        live_retry_cooldown_seconds=600,
    )


def test_sample_replay_advances_and_stops():
    replay = producer.SampleReplay()
    first = replay.next_bar("AAPL")
    second = replay.next_bar("AAPL")

    assert first["timestamp"] < second["timestamp"]
    assert first["ticker"] == "AAPL"

    while replay.next_bar("AAPL") is not None:
        pass
    assert replay.next_bar("AAPL") is None


def test_sample_mode_does_not_call_live_source(monkeypatch):
    monkeypatch.setattr(producer, "fetch_ohlcv", lambda *args, **kwargs: pytest.fail("live called"))

    bar = producer.get_next_bar("MSFT", settings(), producer.SampleReplay(), {})

    assert bar["ticker"] == "MSFT"


def test_auto_mode_sets_cooldown_and_uses_sample(monkeypatch):
    def fail(*args, **kwargs):
        raise FetchError("offline")

    monkeypatch.setattr(producer, "fetch_ohlcv", fail)
    retry_after = {}

    bar = producer.get_next_bar("GOOGL", settings("auto"), producer.SampleReplay(), retry_after)

    assert bar["ticker"] == "GOOGL"
    assert retry_after["GOOGL"] > 0


def test_live_mode_propagates_fetch_failure(monkeypatch):
    monkeypatch.setattr(
        producer,
        "fetch_ohlcv",
        lambda *args, **kwargs: (_ for _ in ()).throw(FetchError("offline")),
    )

    with pytest.raises(FetchError):
        producer.get_next_bar("AAPL", settings("live"), producer.SampleReplay(), {})


def test_publish_bar_adds_json_payload():
    class Client:
        def xadd(self, stream, fields, **kwargs):
            self.call = (stream, fields, kwargs)
            return "1-0"

    client = Client()
    message_id = producer.publish_bar(client, "stock:ohlcv", {"ticker": "AAPL"})

    assert message_id == "1-0"
    assert client.call[0] == "stock:ohlcv"
    assert '"ticker": "AAPL"' in client.call[1]["payload"]


def test_live_startup_returns_full_history_then_only_new_rows(monkeypatch):
    frame = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                ["2026-01-01T10:00:00Z", "2026-01-01T10:05:00Z"]
            ),
            "ticker": ["AAPL", "AAPL"],
            "open": [10, 11],
            "high": [11, 12],
            "low": [9, 10],
            "close": [10.5, 11.5],
            "volume": [100, 200],
        }
    )
    monkeypatch.setattr(producer, "fetch_ohlcv", lambda *args, **kwargs: frame)

    first = producer.get_next_bars(
        "AAPL", settings("live"), producer.SampleReplay(), {}
    )
    later = producer.get_next_bars(
        "AAPL",
        settings("live"),
        producer.SampleReplay(),
        {},
        after_timestamp=first[-1]["timestamp"],
    )

    assert len(first) == 2
    assert all(bar["source"] == "live" for bar in first)
    assert later == []
