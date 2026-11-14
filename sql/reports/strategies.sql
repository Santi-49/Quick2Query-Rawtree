-- Per strategy (model_version before '@'): requests with feedback, clicks, purchases, first answer.
WITH s AS (
    SELECT request_id::String AS rid, any(splitByChar('@', model_version::String)[1]) AS strategy
    FROM {TEAM}.submissions
    GROUP BY rid
),
f AS (
    SELECT request_id::String AS rid, max(clicked::String) AS clicked, max(purchased::String) AS purchased,
           min(ts::DateTime64(3)) AS t
    FROM {TEAM}.feedback
    GROUP BY rid
)
SELECT s.strategy AS strategy, count() AS requests,
       countIf(f.clicked != '') AS clicks, countIf(f.purchased != '') AS purchases,
       toString(min(f.t)) AS since
FROM s INNER JOIN f ON s.rid = f.rid
GROUP BY strategy
ORDER BY requests DESC
