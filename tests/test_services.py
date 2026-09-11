"""Configuration, alerting, and service-health unit tests."""

from contextlib import contextmanager
from types import SimpleNamespace

from src.alerts import notifier
from src.config import Settings
from src.utils import health_check


def test_postgres_dsn_escapes_special_password():
    dsn = Settings(postgres_password="p@ss/word").postgres_dsn

    assert "p%40ss%2Fword" in dsn


def test_maybe_alert_emits_crossover_and_rsi(monkeypatch):
    sent = []
    settings = SimpleNamespace(rsi_overbought=70, rsi_oversold=30)
    monkeypatch.setattr(notifier, "get_settings", lambda: settings)
    monkeypatch.setattr(notifier, "send_alert", lambda subject, body: sent.append(subject))

    notifier.maybe_alert({"ticker": "AAPL", "close": 100, "rsi_14": 75, "sma_cross": 1})

    assert len(sent) == 2
    assert "BULLISH" in sent[0]
    assert "overbought" in sent[1]


def test_overall_health_includes_minio(monkeypatch):
    monkeypatch.setattr(health_check, "check_redis", lambda: {"service": "redis", "ok": True})
    monkeypatch.setattr(health_check, "check_postgres", lambda: {"service": "postgres", "ok": True})
    monkeypatch.setattr(health_check, "check_minio", lambda: {"service": "minio", "ok": True})

    result = health_check.overall_health()

    assert result["status"] == "ok"
    assert {item["service"] for item in result["checks"]} == {"redis", "postgres", "minio"}


def test_service_health_checks_success(monkeypatch):
    class RedisClient:
        def ping(self):
            return True

    class Connection:
        def execute(self, statement):
            return 1

    class Engine:
        @contextmanager
        def connect(self):
            yield Connection()

    class MinioClient:
        def bucket_exists(self, bucket):
            return bucket == "raw-ohlcv"

    monkeypatch.setattr(health_check.redis, "Redis", lambda **kwargs: RedisClient())
    monkeypatch.setattr(health_check, "create_engine", lambda *args, **kwargs: Engine())
    monkeypatch.setattr(health_check, "Minio", lambda *args, **kwargs: MinioClient())

    assert health_check.check_redis()["ok"]
    assert health_check.check_postgres()["ok"]
    assert health_check.check_minio()["ok"]
