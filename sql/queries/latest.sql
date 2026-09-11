-- Latest close and RSI per ticker
SELECT ticker, timestamp, close, rsi_14, sma_cross
FROM processed_indicators
ORDER BY timestamp DESC
LIMIT 50;

-- Bullish crossovers in the last day
SELECT ticker, timestamp, close
FROM processed_indicators
WHERE sma_cross = 1
  AND timestamp > NOW() - INTERVAL '1 day';
