-- Follow-up checks raised by the first pass.

-- history: shown product bought before, by time since the last earlier purchase (slots 1-3, non-home, last 20 days)
SELECT multiIf(gap_h < 24, '1 under 1 day', gap_h < 72, '2 1-3 days', gap_h < 168, '3 3-7 days', gap_h < 720, '4 7-30 days', '5 over 30 days') AS since_last_buy, count() AS shown_n,
       round(100 * countIf(ck = sp) / shown_n, 2) AS ctr, round(100 * countIf(pu = sp) / shown_n, 2) AS conv
FROM (SELECT x.sp AS sp, any(x.ck) AS ck, any(x.pu) AS pu, min(dateDiff('hour', b.bt, x.t)) AS gap_h
      FROM (SELECT request_id::String AS rid, user_id::String AS u, ts::DateTime64(3) AS t, sh[k] AS sp, ck, pu
            FROM (SELECT request_id, user_id, ts, shown::Array(String) AS sh, ifNull(clicked::String, '') AS ck, ifNull(purchased::String, '') AS pu, arrayJoin([1, 2, 3]) AS k
                  FROM shop.history_sessions WHERE context.page::String != 'home' AND ts::DateTime64(3) >= '2026-10-25')) x
      JOIN (SELECT user_id::String AS u, product_id::String AS sp, ts::DateTime64(3) AS bt FROM shop.history_events WHERE event_type::String = 'purchase') b ON b.u = x.u AND b.sp = x.sp
      WHERE b.bt < x.t - INTERVAL 1 HOUR GROUP BY x.rid, x.sp)
GROUP BY since_last_buy ORDER BY since_last_buy;

-- history: number of earlier purchases of the shown product by the user (slots 1-3, non-home, last 20 days)
SELECT least(nb, 5) AS earlier_purchases, count() AS shown_n, round(100 * countIf(ck = sp) / shown_n, 2) AS ctr, round(100 * countIf(pu = sp) / shown_n, 2) AS conv
FROM (SELECT x.sp AS sp, any(x.ck) AS ck, any(x.pu) AS pu, count() AS nb
      FROM (SELECT request_id::String AS rid, user_id::String AS u, ts::DateTime64(3) AS t, sh[k] AS sp, ck, pu
            FROM (SELECT request_id, user_id, ts, shown::Array(String) AS sh, ifNull(clicked::String, '') AS ck, ifNull(purchased::String, '') AS pu, arrayJoin([1, 2, 3]) AS k
                  FROM shop.history_sessions WHERE context.page::String != 'home' AND ts::DateTime64(3) >= '2026-10-25')) x
      JOIN (SELECT user_id::String AS u, product_id::String AS sp, ts::DateTime64(3) AS bt FROM shop.history_events WHERE event_type::String = 'purchase') b ON b.u = x.u AND b.sp = x.sp
      WHERE b.bt < x.t - INTERVAL 1 HOUR GROUP BY x.rid, x.sp)
GROUP BY earlier_purchases ORDER BY earlier_purchases;

-- organic: gap between consecutive purchases of the same product by the same user
SELECT multiIf(gap_h < 1, '0 same hour', gap_h < 24, '1 same day', gap_h < 72, '2 1-3 days', gap_h < 168, '3 3-7 days', gap_h < 720, '4 7-30 days', '5 over 30 days') AS gap, count() AS n
FROM (SELECT dateDiff('hour', lagInFrame(t) OVER w, t) AS gap_h, row_number() OVER w AS rn
      FROM (SELECT user_id::String AS u, product_id::String AS p, ts::DateTime64(3) AS t FROM shop.history_events WHERE event_type::String = 'purchase')
      WINDOW w AS (PARTITION BY u, p ORDER BY t))
WHERE rn > 1 GROUP BY gap ORDER BY gap;

-- live organic: do history buyers of a product buy it again live
SELECT count() AS live_purchases, countIf(b.n > 0) AS bought_before_in_history, countIf(v.n > 0) AS viewed_before_in_history, countIf(h.u != '') AS by_users_in_history
FROM (SELECT user_id::String AS u, product_id::String AS p FROM shop.events WHERE event_type::String = 'purchase') e
LEFT JOIN (SELECT user_id::String AS u, product_id::String AS p, count() AS n FROM shop.history_events WHERE event_type::String = 'purchase' GROUP BY u, p) b USING (u, p)
LEFT JOIN (SELECT user_id::String AS u, product_id::String AS p, count() AS n FROM shop.history_events WHERE event_type::String = 'view' GROUP BY u, p) v USING (u, p)
LEFT JOIN (SELECT DISTINCT user_id::String AS u FROM shop.history_events) h USING u;

-- history organic, same measure on the last 3 hours of history (for comparison with the live row above)
SELECT count() AS purchases, countIf(b.n > 0) AS bought_before, countIf(v.n > 0) AS viewed_before
FROM (SELECT user_id::String AS u, product_id::String AS p FROM shop.history_events WHERE event_type::String = 'purchase' AND ts::DateTime64(3) >= '2026-11-14 04:00:00') e
LEFT JOIN (SELECT user_id::String AS u, product_id::String AS p, count() AS n FROM shop.history_events WHERE event_type::String = 'purchase' AND ts::DateTime64(3) < '2026-11-14 00:00:00' GROUP BY u, p) b USING (u, p)
LEFT JOIN (SELECT user_id::String AS u, product_id::String AS p, count() AS n FROM shop.history_events WHERE event_type::String = 'view' AND ts::DateTime64(3) < '2026-11-14 00:00:00' GROUP BY u, p) v USING (u, p);

-- do slots interact: click rate at slots 2-4 when slot 1 holds a recently viewed product (strong) or not
SELECT has(rv, sh[1]) AS slot1_is_recent_view, count() AS n, round(100 * avg(ck = sh[1]), 2) AS ctr_slot1, round(100 * avg(ck = sh[2]), 3) AS ctr_slot2, round(100 * avg(ck = sh[3]), 3) AS ctr_slot3, round(100 * avg(ck = sh[4]), 3) AS ctr_slot4,
       round(100 * avg(ck != '' AND ck != sh[1]), 2) AS ctr_slots_2_to_10
FROM (SELECT shown::Array(String) AS sh, ifNull(clicked::String, '') AS ck, arrayMap(v -> v.product_id::String, recent_views::Array(JSON)) AS rv FROM shop.history_sessions WHERE context.page::String != 'home'
      AND NOT hasAny(arrayMap(v -> v.product_id::String, recent_views::Array(JSON)), arraySlice(shown::Array(String), 2, 9)))
GROUP BY slot1_is_recent_view;

-- trend group: the products with the largest live lift, with attributes
SELECT l.p AS product, c.category::String AS category, c.subcategory::String AS subcategory, c.brand::String AS brand, c.price_eur::Float64 AS price, l.n AS live_views, round((l.n / l.total) / (h.n / h.total), 2) AS lift, c.description::String AS description
FROM (SELECT product_id::String AS p, count() AS n, (SELECT countIf(event_type::String = 'view') FROM shop.events) AS total FROM shop.events WHERE event_type::String = 'view' GROUP BY p HAVING n >= 150) l
JOIN (SELECT product_id::String AS p, count() AS n, (SELECT countIf(event_type::String = 'view') FROM shop.history_events) AS total FROM shop.history_events WHERE event_type::String = 'view' GROUP BY p) h USING p
JOIN shop.catalog c ON c.product_id::String = l.p
ORDER BY lift DESC LIMIT 14;

-- trend timing: views per 30 minutes of the top trending products
SELECT toStartOfInterval(ts::DateTime64(3), INTERVAL 30 MINUTE) AS t, countIf(product_id::String IN ('p_dbd2ba', 'p_4c1171', 'p_2dca53', 'p_211ab5', 'p_2b0301', 'p_5b3329', 'p_c6f16b', 'p_41923d', 'p_be02e1', 'p_431fa5')) AS trend_views,
       countIf(event_type::String = 'purchase' AND product_id::String IN ('p_dbd2ba', 'p_4c1171', 'p_2dca53', 'p_211ab5', 'p_2b0301', 'p_5b3329', 'p_c6f16b', 'p_41923d', 'p_be02e1', 'p_431fa5')) AS trend_buys, count() AS all_events
FROM shop.events GROUP BY t ORDER BY t;

-- price changes: when, which categories, and organic purchases per view before and after
SELECT u.category::String AS category, count() AS products, min(u.ts::DateTime64(3)) AS first_change, max(u.ts::DateTime64(3)) AS last_change, round(avg(u.price_eur::Float64), 2) AS avg_new_price
FROM shop.catalog_updates u WHERE u.change::String = 'price_change' GROUP BY category ORDER BY products DESC;

-- price changes: organic view share and buy-per-view of the repriced products, before and after
SELECT e.ts::DateTime64(3) >= (SELECT min(ts::DateTime64(3)) FROM shop.catalog_updates WHERE change::String = 'price_change') AS after_change, countIf(event_type::String = 'view') AS views, countIf(repriced AND event_type::String = 'view') AS repriced_views,
       round(100 * repriced_views / views, 2) AS repriced_view_pct, round(100 * countIf(repriced AND event_type::String = 'purchase') / repriced_views, 2) AS repriced_buy_per_view,
       round(100 * countIf(NOT repriced AND event_type::String = 'purchase') / countIf(NOT repriced AND event_type::String = 'view'), 2) AS other_buy_per_view
FROM (SELECT ts, event_type, product_id::String IN (SELECT product_id::String FROM shop.catalog_updates WHERE change::String = 'price_change') AS repriced FROM shop.events) e
GROUP BY after_change ORDER BY after_change;

-- new products: when, attributes, live views and purchases per view compared to the rest
SELECT min(u.ts::DateTime64(3)) AS first_added, max(u.ts::DateTime64(3)) AS last_added, uniqExact(u.subcategory::String) AS subcategories, uniqExact(u.brand::String) AS brands, round(avg(u.price_eur::Float64), 2) AS avg_price,
       (SELECT round(100 * countIf(event_type::String = 'purchase') / countIf(event_type::String = 'view'), 2) FROM shop.events WHERE product_id::String IN (SELECT product_id::String FROM shop.catalog_updates WHERE change::String = 'new_product')) AS new_buy_per_view,
       (SELECT round(100 * countIf(event_type::String = 'purchase') / countIf(event_type::String = 'view'), 2) FROM shop.events) AS all_buy_per_view
FROM shop.catalog_updates u WHERE u.change::String = 'new_product';

-- cold requests as the organisers define them: new shopper, or a recent view of a product added during the event
SELECT count() AS n, round(avg(is_new_user::Bool), 3) AS new_user, round(avg(hasAny(arrayMap(v -> v.product_id::String, recent_views::Array(JSON)), (SELECT groupArray(product_id::String) FROM shop.catalog_updates WHERE change::String = 'new_product'))), 4) AS views_new_product,
       round(avg(is_new_user::Bool OR hasAny(arrayMap(v -> v.product_id::String, recent_views::Array(JSON)), (SELECT groupArray(product_id::String) FROM shop.catalog_updates WHERE change::String = 'new_product'))), 3) AS cold
FROM shop.requests WHERE length(recent_views) > 0 AND ts::DateTime64(3) >= '2026-11-14 11:00:00';

-- request visibility lag right now (server clock minus newest request ts)
SELECT now64(3) AS server_now, max(ts::DateTime64(3)) AS newest_request, dateDiff('millisecond', max(ts::DateTime64(3)), now64(3)) AS lag_ms FROM shop.requests WHERE ts::DateTime64(3) > now() - INTERVAL 1 MINUTE
