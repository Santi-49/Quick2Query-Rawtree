-- Live stream since Saturday 09:00 UTC.

-- requests by page and shopper type
SELECT context.page::String AS page, is_new_user::Bool AS new_user, count() AS n, round(avg(length(recent_views)), 2) AS avg_views, uniqExact(user_id::String) AS users
FROM shop.requests GROUP BY page, new_user ORDER BY page, new_user;

-- cold requests per hour
SELECT toStartOfHour(ts::DateTime64(3)) AS h, count() AS n, round(avg(is_new_user::Bool), 3) AS new_user, round(avg(length(recent_views) = 0), 3) AS no_views, round(avg(is_new_user::Bool AND length(recent_views) = 0), 3) AS new_and_no_views,
       uniqExact(user_id::String) AS users
FROM shop.requests GROUP BY h ORDER BY h;

-- catalogue updates per hour by change
SELECT toStartOfHour(ts::DateTime64(3)) AS h, countIf(change::String = 'new_product') AS new_products, countIf(change::String = 'price_change') AS price_changes, countIf(change::String = 'out_of_stock') AS out_of_stock,
       countIf(change::String = 'back_in_stock') AS back_in_stock, uniqExact(product_id::String) AS products
FROM shop.catalog_updates GROUP BY h ORDER BY h;

-- price changes: size relative to the catalogue price
SELECT count() AS n, round(avg(u.price_eur::Float64 / c.price_eur::Float64), 3) AS avg_ratio, quantilesExact(0.05, 0.25, 0.5, 0.75, 0.95)(round(u.price_eur::Float64 / c.price_eur::Float64, 2)) AS ratio_q, uniqExact(u.product_id::String) AS products
FROM shop.catalog_updates u JOIN shop.catalog c ON c.product_id::String = u.product_id::String WHERE u.change::String = 'price_change';

-- new products: are they in shop.catalog, and how fast do they get views
SELECT count() AS new_products, countIf(c.pid != '') AS already_in_catalog, countIf(v.n > 0) AS with_live_views, sum(v.n) AS live_views, sum(v.buys) AS live_purchases, uniqExact(u.category::String) AS categories,
       round(avgIf(dateDiff('second', u.ts::DateTime64(3), v.first_view), v.n > 0), 0) AS avg_seconds_to_first_view
FROM shop.catalog_updates u
LEFT JOIN (SELECT product_id::String AS pid FROM shop.catalog) c ON c.pid = u.product_id::String
LEFT JOIN (SELECT product_id::String AS p, countIf(event_type::String = 'view') AS n, countIf(event_type::String = 'purchase') AS buys, min(ts::DateTime64(3)) AS first_view FROM shop.events GROUP BY p) v ON v.p = u.product_id::String
WHERE u.change::String = 'new_product';

-- stock: how many products are out now
SELECT count() AS products_changed, countIf(last_change = 'out_of_stock') AS out_now, round(avg(n_out), 2) AS avg_times_out
FROM (SELECT product_id::String AS p, argMax(change::String, ts::DateTime64(3)) AS last_change, countIf(change::String = 'out_of_stock') AS n_out FROM shop.catalog_updates WHERE change::String IN ('out_of_stock', 'back_in_stock') GROUP BY p);

-- live events per hour
SELECT toStartOfHour(ts::DateTime64(3)) AS h, countIf(event_type::String = 'view') AS views, countIf(event_type::String = 'add_to_cart') AS carts, countIf(event_type::String = 'purchase') AS buys, uniqExact(user_id::String) AS users, uniqExact(session_id::String) AS sessions,
       uniqExact(product_id::String) AS products
FROM shop.events GROUP BY h ORDER BY h;

-- trends: top 15 products by lift of live view share over history view share (at least 300 live views)
SELECT l.p AS product, l.n AS live_views, round(1e4 * l.n / l.total, 2) AS live_share_bp, round(1e4 * h.n / h.total, 2) AS hist_share_bp, round((l.n / l.total) / (h.n / h.total), 1) AS lift
FROM (SELECT product_id::String AS p, count() AS n, (SELECT countIf(event_type::String = 'view') FROM shop.events) AS total FROM shop.events WHERE event_type::String = 'view' GROUP BY p HAVING n >= 300) l
JOIN (SELECT product_id::String AS p, count() AS n, (SELECT countIf(event_type::String = 'view') FROM shop.history_events) AS total FROM shop.history_events WHERE event_type::String = 'view' GROUP BY p) h USING p
ORDER BY lift DESC LIMIT 15;

-- trends: how many products moved, among products with at least 100 expected live views
SELECT count() AS products, countIf(lift > 2) AS lift_over_2, countIf(lift > 5) AS lift_over_5, countIf(lift < 0.5) AS lift_under_half, quantilesExact(0.05, 0.5, 0.95)(round(lift, 2)) AS lift_q
FROM (SELECT h.p AS p, (l.n / (SELECT countIf(event_type::String = 'view') FROM shop.events)) / (h.n / (SELECT countIf(event_type::String = 'view') FROM shop.history_events)) AS lift,
             h.n / (SELECT countIf(event_type::String = 'view') FROM shop.history_events) * (SELECT countIf(event_type::String = 'view') FROM shop.events) AS expected
      FROM (SELECT product_id::String AS p, count() AS n FROM shop.history_events WHERE event_type::String = 'view' GROUP BY p) h
      LEFT JOIN (SELECT product_id::String AS p, count() AS n FROM shop.events WHERE event_type::String = 'view' GROUP BY p) l USING p
      WHERE expected >= 100);

-- live view share by category vs history
SELECT c.category::String AS category, round(100 * countIf(src = 'live') / (SELECT countIf(event_type::String = 'view') FROM shop.events), 2) AS live_pct, round(100 * countIf(src = 'hist') / (SELECT countIf(event_type::String = 'view') FROM shop.history_events), 2) AS hist_pct
FROM (SELECT product_id, 'live' AS src FROM shop.events WHERE event_type::String = 'view' UNION ALL SELECT product_id, 'hist' AS src FROM shop.history_events WHERE event_type::String = 'view') e
JOIN shop.catalog c ON c.product_id::String = e.product_id::String GROUP BY category ORDER BY live_pct DESC;

-- new shoppers vs returning: device, region, page
SELECT is_new_user::Bool AS new_user, count() AS n, round(avg(context.device::String = 'android'), 3) AS android, round(avg(context.device::String = 'ios'), 3) AS ios, round(avg(context.region::String IN ('Andalucía', 'Canarias', 'Murcia')), 3) AS south,
       round(avg(context.page::String = 'home'), 3) AS home
FROM shop.requests GROUP BY new_user;

-- requests per live user
SELECT count() AS users, round(avg(n), 2) AS avg_requests, quantilesExact(0.5, 0.9, 0.99)(n) AS q, round(avg(n > 1), 3) AS more_than_one FROM (SELECT user_id::String AS u, count() AS n FROM shop.requests GROUP BY u);

-- are new shoppers in history, and do they have live events before their first request
SELECT is_new_user::Bool AS new_user, uniqExact(r.user_id::String) AS users, uniqExactIf(r.user_id::String, h.u != '') AS in_history
FROM shop.requests r LEFT JOIN (SELECT DISTINCT user_id::String AS u FROM shop.history_events) h ON h.u = r.user_id::String GROUP BY new_user
