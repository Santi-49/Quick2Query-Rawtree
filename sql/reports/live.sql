-- The newest requests with the answer we gave and what the shopper did.
SELECT substring(r.ts::String, 12, 8) AS time, r.context.page::String AS page, r.context.device::String AS device, r.context.region::String AS region,
       r.is_new_user::Bool AS new_shopper, length(r.recent_views::Array(JSON)) AS views,
       s.model_version AS model_version, f.served_by AS served_by, f.latency_ms AS latency_ms,
       f.clicked != '' AS clicked, f.purchased != '' AS purchased
FROM (SELECT * FROM shop.requests WHERE ts::DateTime64(3) > now64(3) - INTERVAL 5 MINUTE) r
LEFT JOIN (SELECT request_id::String AS rid, any(model_version::String) AS model_version FROM {TEAM}.submissions GROUP BY rid) s ON s.rid = r.request_id::String
LEFT JOIN (SELECT request_id::String AS rid, any(served_by::String) AS served_by, any(toFloat64OrZero(toString(latency_ms))) AS latency_ms,
                  any(clicked::String) AS clicked, any(purchased::String) AS purchased
           FROM {TEAM}.feedback WHERE ts::DateTime64(3) > now64(3) - INTERVAL 6 MINUTE GROUP BY rid) f ON f.rid = r.request_id::String
ORDER BY r.ts DESC
