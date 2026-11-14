-- Last 3 hours, requests answered by us: page x new/returning shopper x model_version, with clicks and purchases.
WITH f AS (
    SELECT request_id::String AS rid,
           max(served_by::String) AS served_by,
           max(clicked::String) AS clicked,
           max(purchased::String) AS purchased
    FROM {TEAM}.feedback
    WHERE ts::DateTime64(3) > now64(3) - INTERVAL 3 HOUR
    GROUP BY rid
),
s AS (
    SELECT request_id::String AS rid, any(model_version::String) AS model_version
    FROM {TEAM}.submissions
    WHERE request_id::String IN (SELECT rid FROM f)
    GROUP BY rid
),
r AS (
    SELECT request_id::String AS rid, any(context.page::String) AS page, any(is_new_user::Bool) AS new_user
    FROM shop.requests
    WHERE ts::DateTime64(3) > now64(3) - INTERVAL 3 HOUR - INTERVAL 1 MINUTE
    GROUP BY rid
)
SELECT r.page AS page, r.new_user AS new_user, s.model_version AS model_version,
       count() AS requests,
       countIf(f.clicked != '') AS clicks,
       countIf(f.purchased != '') AS purchases
FROM f
INNER JOIN s ON s.rid = f.rid
INNER JOIN r ON r.rid = f.rid
WHERE f.served_by = 'team'
GROUP BY page, new_user, model_version
ORDER BY page, new_user, requests DESC
