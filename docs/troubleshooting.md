# Troubleshooting

## `docker compose` cannot reach Redis / Postgres

Inside Compose, hosts must be service names (`redis`, `postgres`). Those are injected in `docker-compose.yml`. On the host, keep `localhost` in `.env`.

## yfinance returns an empty frame

In `auto` mode the fetcher retries, enters a cooldown, and advances through the sample CSV. Check ticker spelling (`RELIANCE.NS` vs `RELIANCE`) and use `DATA_SOURCE=sample` for deterministic demos.

## Dashboard is empty

If Postgres is empty, Streamlit loads `data/sample/ohlcv_sample.csv`. If you still see nothing, confirm the CSV path relative to the working directory (`/app` in Docker).

## MinIO write errors

Wait for `minio-init` to create `raw-ohlcv`. Re-run:

```bash
docker compose up minio-init
```

## Consumer never ACKs

Transient failures remain pending and are reclaimed after the configured idle period. After the configured attempt limit, the message moves to `stock:ohlcv:dead-letter`. Inspect it with:

```bash
docker compose exec redis redis-cli XRANGE stock:ohlcv:dead-letter - +
```

## Health check red

`src/utils/health_check.py` uses a 2s Redis timeout. If you just started Compose, wait for `healthy` on Redis and Postgres.

## Email never sends

`ENABLE_EMAIL_ALERTS` defaults to false. Alerts still log at INFO so students can grade the trigger path without a mailbox.
