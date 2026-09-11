# API reference

## `fetch_ohlcv(ticker, period, interval)`

Downloads OHLCV via yfinance with three Tenacity retries. Returns a DataFrame with `timestamp, ticker, open, high, low, close, volume, ingested_at`.

In `auto` mode, repeated failure starts a live-source cooldown while the producer replays `data/sample/ohlcv_sample.csv` in timestamp order.

## `publish_bar(client, stream, bar)`

`XADD`s a JSON payload onto Redis Streams with a configurable approximate maximum length (one million by default).

## `importer`

`python -m src.ingestion.importer --file <path>` validates a CSV/Parquet file, streams it through Redis in bounded batches, and waits for the consumer group to drain. Imported messages use `source=local`.

## `process_payload(payload)`

Validates with `OHLCVBar`, writes immutable Parquet, upserts Postgres, loads recent ticker history, computes indicators, and may alert.

## `sma` / `rsi` / `macd` / `bollinger_bands`

Pure pandas implementations in `src/processing/indicators.py`. RSI uses Wilder-style EMA smoothing.

## `sma_crossover`

Uses `shift(1)` so a cross is detected on the bar *after* the relationship changes — the usual “previous vs current” pattern interviewers ask about.

## Health

`overall_health()` checks Redis, Postgres, and the configured MinIO bucket. The dashboard shows **sample mode** when Postgres has no usable data so demos never go blank.
