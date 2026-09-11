# WorkForge handoff

This repository is a standalone application artifact. WorkForge launches the build environment, but the completed repository has no WorkForge runtime dependency.

## Platform runtime

Use deterministic settings inside the simulated workspace:

```text
DATA_SOURCE=sample
POLL_INTERVAL_SECONDS=0.1
ENABLE_EMAIL_ALERTS=false
```

Expose these workspace previews:

| Preview | Port | Audience |
| --- | ---: | --- |
| Streamlit application | 8501 | Learner-facing finished UI |
| MinIO console | 9001 | Optional engineering/storage inspection |

Health endpoints:

- Application: `http://localhost:8501/_stcore/health`
- MinIO: `http://localhost:9000/minio/health/live`

The platform evaluation can run `make test`, `make lint`, and `make e2e`. Sample mode supplies 80 bars for each bundled ticker, enough to prove SMA-50 warmup and full dual-storage behavior.

## Learner export

Export the completed repository without `.env`, virtual environments, Docker volumes, dbt targets, generated docs, or private datasets. The learner can then run:

```bash
cp .env.example .env
docker compose up -d --build
make import-data FILE=/absolute/path/to/their-dataset.csv
```

The resulting application runs independently at `http://localhost:8501` and clearly labels bundled sample, imported local, legacy, and live market data.

## Resource profile

Recommended minimum for the complete Compose stack:

- 4 CPU cores
- 6 GB RAM
- 10 GB free disk
- Docker-compatible workspace runtime

If the WorkForge sandbox cannot run nested Docker, provision Redis, PostgreSQL, and S3-compatible storage as workspace services and inject the same environment variables from `.env.example`.
