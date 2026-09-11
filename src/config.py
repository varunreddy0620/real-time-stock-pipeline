"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"
    tickers: str = "AAPL,MSFT,GOOGL"
    poll_interval_seconds: float = 5.0
    ohlcv_interval: str = "5m"
    lookback_period: str = "1d"
    data_source: str = Field(default="auto", pattern="^(auto|live|sample)$")
    live_retry_cooldown_seconds: float = Field(default=600.0, ge=1)
    indicator_max_gap_seconds: int = Field(default=86_400, ge=60)

    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_stream: str = "stock:ohlcv"
    redis_stream_maxlen: int = Field(default=1_000_000, ge=10_000)
    redis_consumer_group: str = "pipeline"
    redis_consumer_name: str = "worker-1"
    redis_pending_idle_ms: int = Field(default=60_000, ge=1_000)
    redis_max_delivery_attempts: int = Field(default=3, ge=1)
    redis_dead_letter_stream: str = "stock:ohlcv:dead-letter"

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "market"
    postgres_user: str = "pipeline"
    postgres_password: str = "pipeline"

    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "raw-ohlcv"
    minio_secure: bool = False

    sendgrid_api_key: str = ""
    alert_from_email: str = "alerts@example.com"
    alert_to_email: str = "you@example.com"
    enable_email_alerts: bool = False
    rsi_overbought: float = 70.0
    rsi_oversold: float = 30.0

    dashboard_default_ticker: str = "AAPL"

    @property
    def ticker_list(self) -> list[str]:
        return [t.strip().upper() for t in self.tickers.split(",") if t.strip()]

    @property
    def postgres_dsn(self) -> str:
        return URL.create(
            drivername="postgresql",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        ).render_as_string(hide_password=False)

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/0"


@lru_cache
def get_settings() -> Settings:
    return Settings()
