-- H-gap. The per-impression classification runs in Python on these pulls (eda/gap/pull.py, pull_carts.py,
-- build.py, report.py); chunk c = 0..7 by cityHash64(user_id) % 8. The last statements run as they are.

-- pull: our feedback joined to its request (chunk 0 shown)
SELECT f.id AS request_id, r.u AS user_id, r.t AS req_ts, r.new AS is_new, r.page AS page, r.device AS device, r.region AS region,
       r.views AS views, r.vts AS view_ts, f.shown AS shown, f.clicked AS clicked, f.purchased AS purchased, f.mv AS model_version
FROM (SELECT request_id::String AS id, shown::Array(String) AS shown, clicked::String AS clicked, purchased::String AS purchased,
             model_version::String AS mv FROM {TEAM}.feedback) AS f
INNER JOIN (SELECT request_id::String AS id, user_id::String AS u, toUnixTimestamp64Milli(ts::DateTime64(3, 'UTC')) AS t, is_new_user::Bool AS new,
                   context.page::String AS page, context.device::String AS device, context.region::String AS region,
                   arrayMap(v -> v.product_id::String, recent_views::Array(JSON)) AS views,
                   arrayMap(v -> toUnixTimestamp64Milli(v.ts::DateTime64(3, 'UTC')), recent_views::Array(JSON)) AS vts
            FROM shop.requests WHERE cityHash64(user_id::String) % 8 = 0) AS r ON f.id = r.id;

-- pull: today's organic events of shoppers who made requests (chunk 0 shown)
SELECT user_id::String AS user_id, session_id::String AS session_id, event_type::String AS et, product_id::String AS product_id,
       price_eur::Float64 AS price, toUnixTimestamp64Milli(ts::DateTime64(3, 'UTC')) AS ts
FROM shop.events
WHERE cityHash64(user_id::String) % 8 = 0
  AND user_id::String IN (SELECT user_id::String FROM shop.requests WHERE cityHash64(user_id::String) % 8 = 0);

-- pull: history carts not bought, with last cart time (chunk 0 shown)
SELECT user_id::String AS user_id, product_id::String AS product_id, countIf(event_type::String = 'add_to_cart') AS carts,
       toUnixTimestamp64Milli(maxIf(ts::DateTime64(3, 'UTC'), event_type::String = 'add_to_cart')) AS last_cart,
       countIf(event_type::String = 'view') AS views, countIf(event_type::String = 'purchase') AS buys
FROM shop.history_events
WHERE cityHash64(user_id::String) % 8 = 0
  AND user_id::String IN (SELECT user_id::String FROM shop.requests WHERE cityHash64(user_id::String) % 8 = 0)
GROUP BY user_id, product_id HAVING carts > 0 AND buys = 0;

-- history carousel by page
SELECT context.page::String AS page, count() AS n, countIf(purchased::String != '') / count() AS buy, countIf(clicked::String != '') / count() AS ctr
FROM shop.history_sessions GROUP BY page;

-- history carousel: purchases by relation of the shown product, non-home, 1/8 of shoppers
WITH s AS (
  SELECT request_id::String AS id, user_id::String AS u, ts::DateTime64(3) AS t,
         arrayMap(v -> v.product_id::String, recent_views::Array(JSON)) AS views, shown::Array(String) AS shown, ifNull(purchased::String, '') AS bought
  FROM shop.history_sessions WHERE cityHash64(user_id::String) % 8 = 0 AND context.page::String != 'home'),
cat AS (SELECT product_id::String AS cp, category::String AS cc FROM shop.catalog),
hb AS (SELECT user_id::String AS bu, product_id::String AS bp, min(ts::DateTime64(3)) AS bt FROM shop.history_events
       WHERE event_type::String = 'purchase' AND cityHash64(user_id::String) % 8 = 0 GROUP BY bu, bp),
x AS (SELECT s.u AS xu, s.t AS xt, arrayJoin(arrayEnumerate(s.shown)) AS k, s.shown[k] AS xp, s.views AS views, s.views[-1] AS last,
             toUInt8(s.bought = s.shown[k]) AS buy FROM s)
SELECT multiIf(hb.bu != '' AND hb.bt < x.xt, 'bought before', has(views, xp), 'recent view', c1.cc = c2.cc, 'same category as last view', 'other') AS rel,
       count() AS imps, round(sum(1 / log2(k + 1))) AS sw, sum(buy) AS buys, round(100 * buys / sw, 3) AS wconv
FROM x
LEFT JOIN cat AS c1 ON c1.cp = x.xp
LEFT JOIN cat AS c2 ON c2.cp = x.last
LEFT JOIN hb ON hb.bu = x.xu AND hb.bp = x.xp
GROUP BY rel ORDER BY rel;

-- price changes by category and time
SELECT category::String AS c, count() AS n, min(ts::DateTime64(3)) AS a, max(ts::DateTime64(3)) AS b
FROM shop.catalog_updates WHERE change::String = 'price_change' GROUP BY c;
