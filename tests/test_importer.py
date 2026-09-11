"""Local CSV/Parquet dataset validation and publishing tests."""

import json

import pandas as pd
import pytest

from src.ingestion.importer import (
    DatasetValidationError,
    iter_validated_bars,
    publish_dataset,
    validate_dataset,
    wait_until_consumed,
)


def dataset_frame():
    return pd.DataFrame(
        {
            "timestamp": ["2026-01-01T10:00:00Z", "2026-01-01T10:05:00Z"],
            "ticker": ["aapl", "aapl"],
            "open": [10, 11],
            "high": [11, 12],
            "low": [9, 10],
            "close": [10.5, 11.5],
            "volume": [100, 110],
        }
    )


@pytest.mark.parametrize("extension", ["csv", "parquet"])
def test_validate_supported_dataset_formats(tmp_path, extension):
    path = tmp_path / f"bars.{extension}"
    frame = dataset_frame()
    if extension == "csv":
        frame.to_csv(path, index=False)
    else:
        frame.to_parquet(path, index=False)

    summary = validate_dataset(path, batch_size=1)
    bars = list(iter_validated_bars(path, batch_size=1))

    assert summary["rows"] == 2
    assert summary["tickers"] == ["AAPL"]
    assert bars[0]["source"] == "local"


def test_dataset_rejects_missing_columns(tmp_path):
    path = tmp_path / "bad.csv"
    pd.DataFrame({"timestamp": ["2026-01-01"], "ticker": ["AAPL"]}).to_csv(path, index=False)

    with pytest.raises(DatasetValidationError, match="Missing required columns"):
        validate_dataset(path)


def test_dataset_rejects_out_of_order_ticker_rows(tmp_path):
    path = tmp_path / "unsorted.csv"
    frame = dataset_frame().iloc[::-1]
    frame.to_csv(path, index=False)

    with pytest.raises(DatasetValidationError, match="not sorted"):
        validate_dataset(path)


def test_publish_dataset_batches_redis_messages(tmp_path):
    path = tmp_path / "bars.csv"
    dataset_frame().to_csv(path, index=False)

    class Pipeline:
        def __init__(self):
            self.messages = []
            self.executions = 0

        def xadd(self, stream, fields, **kwargs):
            self.messages.append((stream, fields, kwargs))

        def execute(self):
            self.executions += 1

    class Client:
        def __init__(self):
            self.pipe = Pipeline()

        def pipeline(self, transaction=False):
            return self.pipe

    client = Client()
    summary = publish_dataset(client, path, "stock:ohlcv", 100_000, batch_size=1, batch_delay_seconds=0)

    assert summary["rows"] == 2
    assert client.pipe.executions == 3
    payload = json.loads(client.pipe.messages[0][1]["payload"])
    assert payload["source"] == "local"


def test_wait_until_consumed_returns_when_group_is_drained():
    class Client:
        def xinfo_groups(self, stream):
            return [{"name": "pipeline", "lag": 0, "pending": 0}]

    wait_until_consumed(Client(), "stock:ohlcv", "pipeline", timeout_seconds=1, poll_seconds=0)
