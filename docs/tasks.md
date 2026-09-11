# 17-task map

Each course task maps to files in this repository so students always know where to type.

## Module 1 — Setup & ingestion

| Task | Title | Primary files |
| --- | --- | --- |
| 1 | Project scaffolding | repo layout, `.gitignore` |
| 2 | Environment & dependencies | `requirements.txt`, `.env.example` |
| 3 | API integration | `src/ingestion/fetcher.py` |

## Module 2 — Streaming & storage

| Task | Title | Primary files |
| --- | --- | --- |
| 4 | Real-time producer | `src/ingestion/producer.py` |
| 5 | Message consumer | `src/processing/consumer.py`, `schema.py` |
| 6 | Raw data storage | `src/storage/minio_writer.py` |
| 7 | Logging & monitoring | `src/utils/logging_config.py`, `health_check.py` |

## Module 3 — Processing & database

| Task | Title | Primary files |
| --- | --- | --- |
| 8 | Data cleaning | `src/processing/cleaner.py` |
| 9 | Technical indicators | `src/processing/indicators.py`, `tests/test_indicators.py` |
| 10 | Database modeling | `sql/schema.sql` |
| 11 | dbt transformations | `dbt_project/models/` |

## Module 4 — Dashboard & alerts

| Task | Title | Primary files |
| --- | --- | --- |
| 12 | Streamlit dashboard | `src/dashboard/app.py` |
| 13 | Crossover detection | `src/processing/signals.py` |
| 14 | Email alerts | `src/alerts/notifier.py` |

## Module 5 — Deployment & polish

| Task | Title | Primary files |
| --- | --- | --- |
| 15 | Dockerization | `Dockerfile`, `docker-compose.yml` |
| 16 | CI/CD | `.github/workflows/ci.yml` |
| 17 | README & documentation | `README.md`, `docs/` |

!!! tip "Teaching pattern"
    Fill-in-the-blank exercises should hide one real line (for example the `xadd` call) rather than an entire file. Students still run the rest of the stack.
