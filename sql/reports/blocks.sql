-- Per 10-minute block (t - 600 s, t], t = 395 s past a 600 s epoch boundary: requests and our feedback.
WITH r AS (
    SELECT request_id::String AS rid,
           toInt64(ceil((toUnixTimestamp64Milli(ts::DateTime64(3)) / 1000 - 395) / 600)) AS slot
    FROM shop.requests
    WHERE ts::DateTime64(3) > toDateTime64('{SINCE}', 3)
),
f AS (
    SELECT request_id::String AS rid,
           max(served_by::String) AS served_by,
           max(clicked::String) AS clicked,
           max(purchased::String) AS purchased
    FROM {TEAM}.feedback
    WHERE ts::DateTime64(3) > toDateTime64('{SINCE}', 3)
    GROUP BY rid
)
SELECT r.slot AS slot,
       count() AS requests,
       countIf(f.rid != '') AS fed,
       countIf(f.served_by = 'team') AS answered,
       countIf(f.clicked != '') AS clicks,
       countIf(f.purchased != '') AS purchases
FROM r LEFT JOIN f ON r.rid = f.rid
GROUP BY slot
ORDER BY slot
