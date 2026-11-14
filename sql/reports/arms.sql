-- Per 10-minute block: how many of its requests each of our model_versions answered.
WITH r AS (
    SELECT request_id::String AS rid,
           toInt64(ceil((toUnixTimestamp64Milli(ts::DateTime64(3)) / 1000 - 395) / 600)) AS slot
    FROM shop.requests
    WHERE ts::DateTime64(3) > toDateTime64('{SINCE}', 3)
),
s AS (
    SELECT request_id::String AS rid, any(model_version::String) AS model_version
    FROM {TEAM}.submissions
    WHERE request_id::String IN (SELECT rid FROM r)
    GROUP BY rid
)
SELECT r.slot AS slot, s.model_version AS model_version, count() AS n
FROM r INNER JOIN s ON r.rid = s.rid
GROUP BY slot, model_version
ORDER BY slot, n DESC
