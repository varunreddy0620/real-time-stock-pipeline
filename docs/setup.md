# Setup

## Prerequisites

- Docker Desktop (or Docker Engine + Compose v2)
- Python 3.11+ if you want a local virtualenv for tests/docs
- Optional: SendGrid API key for live email

## One-command stack

```bash
cp .env.example .env
docker compose up --build
```

Compose starts Redis, PostgreSQL, MinIO, the producer, the consumer, and Streamlit.

For a deterministic demo that fills indicator windows quickly, set these values in `.env` before starting:

```text
DATA_SOURCE=sample
POLL_INTERVAL_SECONDS=0.1
```

`auto` tries live data and enters a configurable cooldown before retrying after a failure; `live` disables fallback.

## Local tests and docs (no Docker required for unit tests)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
pytest
mkdocs serve -a 127.0.0.1:8000
```

## Environment

`.env.example` is the template. Docker services override hosts (`redis`, `postgres`, `minio`) so the same file works on a laptop (`localhost`).

| Variable | Purpose |
| --- | --- |
| `TICKERS` | Comma-separated symbols |
| `POLL_INTERVAL_SECONDS` | Producer loop delay |
| `DATA_SOURCE` | `auto`, `live`, or deterministic `sample` replay |
| `LIVE_RETRY_COOLDOWN_SECONDS` | Delay before retrying a failed live source |
| `ENABLE_EMAIL_ALERTS` | Must be true plus `SENDGRID_API_KEY` to send mail |

## Services cheat sheet

| Service | Port |
| --- | --- |
| Streamlit | 8501 |
| Postgres | 5432 |
| Redis | 6379 |
| MinIO API | 9000 |
| MinIO console | 9001 |

## dbt

From `dbt_project/`:

```bash
dbt build --profiles-dir .
```

Requires Postgres to be up and `raw_ohlcv` to contain rows.

## End-to-end check

After at least 50 bars per ticker are present:

```bash
make e2e
```

## Import a learner dataset

```bash
make validate-data FILE=/absolute/path/to/ohlcv.csv
make import-data FILE=/absolute/path/to/ohlcv.csv
```

CSV and Parquet are supported. See [Local datasets](local-datasets.md) for the schema and operational guidance.
