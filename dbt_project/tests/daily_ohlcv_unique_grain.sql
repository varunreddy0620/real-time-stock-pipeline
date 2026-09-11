SELECT ticker, trade_date
FROM {{ ref('daily_ohlcv') }}
GROUP BY ticker, trade_date
HAVING COUNT(*) > 1
