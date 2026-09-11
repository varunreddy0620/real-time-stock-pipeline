#!/usr/bin/env bash
set -euo pipefail

docker compose config --quiet
docker compose ps --status running
curl --fail --silent --show-error http://localhost:8501/_stcore/health >/dev/null

pending="$(docker compose exec -T redis redis-cli XPENDING stock:ohlcv pipeline | head -1)"
test "${pending}" = "0"

docker compose exec -T postgres psql -U "${POSTGRES_USER:-pipeline}" -d "${POSTGRES_DB:-market}" -c \
  "SELECT ticker, COUNT(*) raw_rows FROM raw_ohlcv GROUP BY ticker ORDER BY ticker"
docker compose exec -T postgres psql -U "${POSTGRES_USER:-pipeline}" -d "${POSTGRES_DB:-market}" -c \
  "SELECT ticker, COUNT(sma_50) ready_sma50, COUNT(rsi_14) ready_rsi FROM processed_indicators GROUP BY ticker ORDER BY ticker"

minimum_raw="$(docker compose exec -T postgres psql -U "${POSTGRES_USER:-pipeline}" -d "${POSTGRES_DB:-market}" -tAc \
  "SELECT COALESCE(MIN(row_count), 0) FROM (SELECT COUNT(*) row_count FROM raw_ohlcv GROUP BY ticker) counts")"
minimum_indicators="$(docker compose exec -T postgres psql -U "${POSTGRES_USER:-pipeline}" -d "${POSTGRES_DB:-market}" -tAc \
  "SELECT COALESCE(MIN(row_count), 0) FROM (SELECT COUNT(*) row_count FROM processed_indicators GROUP BY ticker) counts")"
ready_sma50="$(docker compose exec -T postgres psql -U "${POSTGRES_USER:-pipeline}" -d "${POSTGRES_DB:-market}" -tAc \
  "SELECT COALESCE(MIN(row_count), 0) FROM (SELECT COUNT(sma_50) row_count FROM processed_indicators GROUP BY ticker) counts")"

test "${minimum_raw}" -ge 50
test "${minimum_indicators}" -ge 50
test "${ready_sma50}" -gt 0

(
  cd dbt_project
  ../.venv/bin/dbt build --profiles-dir .
)

echo "End-to-end checks passed. Dashboard: http://localhost:8501"
