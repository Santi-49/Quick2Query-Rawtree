-- Explore arm per stratum: requests with feedback, clicks, purchases, mean pool size.
WITH e AS (
    SELECT request_id::String AS rid, any(stratum::String) AS stratum, any(toFloat64OrZero(toString(pool))) AS pool
    FROM {TEAM}.scratch
    WHERE kind::String = 'explore'
    GROUP BY rid
),
f AS (
    SELECT request_id::String AS rid, max(clicked::String) AS clicked, max(purchased::String) AS purchased
    FROM {TEAM}.feedback
    GROUP BY rid
)
SELECT e.stratum AS stratum, count() AS requests,
       countIf(f.clicked != '') AS clicks, countIf(f.purchased != '') AS purchases,
       avg(e.pool) AS pool
FROM e INNER JOIN f ON e.rid = f.rid
GROUP BY stratum
ORDER BY requests DESC
