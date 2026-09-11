SELECT
    ticker,
    DATE_TRUNC('week', timestamp) AS week_start,
    AVG(close) AS avg_close,
    STDDEV(close) AS close_volatility,
    SUM(volume) AS weekly_volume
FROM {{ source('public', 'raw_ohlcv') }}
GROUP BY ticker, DATE_TRUNC('week', timestamp)
