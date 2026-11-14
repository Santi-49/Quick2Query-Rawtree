-- Carousel history joined to what the same user did before (organic events).
-- Bought-before and viewed-before splits are in 03f-rebuy.sql (unmatched left-join rows are defaults, not NULL).

-- home page: conversion when the shown category is the user's most viewed category (all history, mild leakage)
SELECT if(c.category::String = t.top_cat, '1 user top category', '2 other category') AS state, count() AS n, round(100 * countIf(isNotNull(x.clicked)) / n, 2) AS ctr, round(100 * countIf(isNotNull(x.purchased)) / n, 2) AS conv
FROM (SELECT user_id::String AS u, (shown::Array(String))[1] AS sp, clicked, purchased FROM shop.history_sessions WHERE context.page::String = 'home') x
JOIN shop.catalog c ON c.product_id::String = x.sp
JOIN (SELECT u, argMax(cat, n) AS top_cat FROM (SELECT e.user_id::String AS u, c.category::String AS cat, count() AS n FROM shop.history_events e JOIN shop.catalog c ON c.product_id::String = e.product_id::String WHERE e.event_type::String = 'view' GROUP BY u, cat) GROUP BY u) t USING u
GROUP BY state ORDER BY state;

-- android in the south: by shown category (non-home)
SELECT c.category::String AS category, countIf(seg) AS n_seg, round(100 * countIf(seg AND isNotNull(x.purchased)) / n_seg, 2) AS conv_android_south, round(100 * countIf(NOT seg AND isNotNull(x.purchased)) / countIf(NOT seg), 2) AS conv_rest,
       round(100 * countIf(seg AND isNotNull(x.clicked)) / n_seg, 2) AS ctr_android_south, round(100 * countIf(NOT seg AND isNotNull(x.clicked)) / countIf(NOT seg), 2) AS ctr_rest, round(n_seg / count(), 3) AS seg_share
FROM (SELECT (shown::Array(String))[1] AS sp, clicked, purchased, context.device::String = 'android' AND context.region::String IN ('Andalucía', 'Canarias', 'Murcia') AS seg FROM shop.history_sessions WHERE context.page::String != 'home') x
JOIN shop.catalog c ON c.product_id::String = x.sp GROUP BY category ORDER BY n_seg DESC;

-- do carousel purchases show up in the organic events (same user and product within 10 minutes)
SELECT count() AS carousel_purchases, countIf(isNotNull(e.t)) AS matched_purchase_events
FROM (SELECT user_id::String AS u, purchased::String AS p, ts::DateTime64(3) AS t FROM shop.history_sessions WHERE isNotNull(purchased) AND ts::DateTime64(3) >= '2026-11-01') x
LEFT JOIN (SELECT user_id::String AS u, product_id::String AS p, ts::DateTime64(3) AS t FROM shop.history_events WHERE event_type::String = 'purchase' AND ts::DateTime64(3) >= '2026-11-01') e
  ON e.u = x.u AND e.p = x.p AND abs(dateDiff('second', e.t, x.t)) < 600;

-- do recent views match the user's organic view events just before the request
SELECT count() AS requests, countIf(isNotNull(e.t)) AS last_view_found_in_events
FROM (SELECT user_id::String AS u, (recent_views::Array(JSON))[-1].product_id::String AS p, (recent_views::Array(JSON))[-1].ts::DateTime64(3) AS vt FROM shop.history_sessions WHERE length(recent_views) > 0 AND ts::DateTime64(3) >= '2026-11-13') x
LEFT JOIN (SELECT user_id::String AS u, product_id::String AS p, ts::DateTime64(3) AS t FROM shop.history_events WHERE event_type::String = 'view' AND ts::DateTime64(3) >= '2026-11-12') e
  ON e.u = x.u AND e.p = x.p AND e.t = x.vt;

-- user long-term affinity: shown product's subcategory share in the user's past views (slot 1, non-home, product not in recent views)
SELECT multiIf(isNull(a.n) OR a.n = 0, '0 never viewed subcategory', a.n < 5, '1 1-4 views', a.n < 20, '2 5-19 views', '3 20+ views') AS user_subcat_views, count() AS shown_n,
       round(100 * countIf(ck = sp) / shown_n, 2) AS ctr, round(100 * countIf(pu = sp) / shown_n, 2) AS conv
FROM (SELECT x.u AS u, x.sp AS sp, x.ck AS ck, x.pu AS pu, c.subcategory::String AS sub
      FROM (SELECT user_id::String AS u, (shown::Array(String))[1] AS sp, ifNull(clicked::String, '') AS ck, ifNull(purchased::String, '') AS pu
            FROM shop.history_sessions WHERE context.page::String != 'home' AND ts::DateTime64(3) >= '2026-11-01' AND NOT has(arrayMap(v -> v.product_id::String, recent_views::Array(JSON)), (shown::Array(String))[1])) x
      JOIN shop.catalog c ON c.product_id::String = x.sp) y
LEFT JOIN (SELECT e.user_id::String AS u, c.subcategory::String AS sub, count() AS n FROM shop.history_events e JOIN shop.catalog c ON c.product_id::String = e.product_id::String WHERE e.event_type::String = 'view' AND e.ts::DateTime64(3) < '2026-11-01' GROUP BY u, sub) a USING (u, sub)
GROUP BY user_subcat_views ORDER BY user_subcat_views
