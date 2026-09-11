# Local datasets

The completed application can ingest a learner-owned CSV or Parquet dataset without changing code or bypassing the pipeline.

## Required schema

| Column | Meaning |
| --- | --- |
| `timestamp` | ISO-8601 timestamp; timezone recommended |
| `ticker` | Symbol, up to 16 characters |
| `open` | Positive opening price |
| `high` | Must be at least open and close |
| `low` | Must be at most open and close |
| `close` | Positive closing price |
| `volume` | Non-negative traded volume |

Rows must be in ascending timestamp order within each ticker. Tickers may be interleaved or grouped. Column names are case-insensitive.

Use `data/sample/ohlcv_template.csv` as the smallest template. CSV is read in chunks; Parquet is read in record batches, so large files are not loaded entirely into memory.

## Import

Start the stack and optionally stop live publication while importing:

```bash
docker compose up -d
docker compose stop producer
make validate-data FILE=/absolute/path/to/market-data.parquet
make import-data FILE=/absolute/path/to/market-data.parquet
docker compose start producer
```

Validation runs before publication. The importer labels rows as `local`, publishes them to Redis in batches, and waits until the consumer has written them to PostgreSQL and MinIO.

Duplicate ticker/timestamp pairs are safe: PostgreSQL updates the existing row, while MinIO preserves each ingestion event for auditability.

## Private data

Dataset files under `data/import/` are ignored by Git. Never commit licensed or private market data. The bundled sample is synthetic and exists only for demos and automated evaluation.

## Troubleshooting

- `Missing required columns`: rename fields to the required schema.
- `not sorted by timestamp`: sort ascending within each ticker before import.
- `Invalid data at row`: inspect the reported price/volume rule.
- Consumer timeout: inspect `docker compose logs consumer` and the dead-letter stream.
