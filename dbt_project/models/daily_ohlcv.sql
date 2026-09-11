SELECT
    ticker,
    DATE_TRUNC('day', timestamp) AS trade_date,
    MIN(timestamp) AS first_ts,
    MAX(timestamp) AS last_ts,
    (ARRAY_AGG(open ORDER BY timestamp))[1] AS open,
    MAX(high) AS high,
    MIN(low) AS low,
    (ARRAY_AGG(close ORDER BY timestamp DESC))[1] AS close,
    SUM(volume) AS volume
FROM {{ source('public', 'raw_ohlcv') }}
GROUP BY ticker, DATE_TRUNC('day', timestamp)
