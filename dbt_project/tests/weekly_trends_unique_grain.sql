SELECT ticker, week_start
FROM {{ ref('weekly_trends') }}
GROUP BY ticker, week_start
HAVING COUNT(*) > 1
