-- Organic history (shop.history_events, 12M events over 60 days).

-- sessions: size and funnel
SELECT count() AS sessions, round(avg(views), 2) AS avg_views, quantilesExact(0.5, 0.9, 0.99)(views) AS views_q, round(avg(carts > 0), 3) AS with_cart, round(avg(buys > 0), 3) AS with_purchase,
       round(avg(buys), 3) AS buys_per_session, max(buys) AS max_buys, round(avg(dur), 0) AS avg_seconds, round(avg(ncat), 2) AS avg_categories, round(avg(ncat = 1), 3) AS one_category
FROM (SELECT session_id::String AS s, countIf(event_type::String = 'view') AS views, countIf(event_type::String = 'add_to_cart') AS carts, countIf(event_type::String = 'purchase') AS buys,
             dateDiff('second', min(ts::DateTime64(3)), max(ts::DateTime64(3))) AS dur, uniqExact(c.category::String) AS ncat
      FROM shop.history_events e JOIN shop.catalog c ON c.product_id::String = e.product_id::String GROUP BY s);

-- users: sessions, devices, regions
SELECT count() AS users, round(avg(sessions), 1) AS avg_sessions, quantilesExact(0.1, 0.5, 0.9, 0.99)(sessions) AS sessions_q, round(avg(devices = 1), 3) AS one_device, round(avg(regions = 1), 3) AS one_region,
       round(avg(buys > 0), 3) AS buyers, round(avg(buys), 2) AS avg_buys, round(avg(top_cat_share), 3) AS avg_top_category_share, round(avg(ncat), 2) AS avg_categories
FROM (SELECT u, sum(n) AS views, max(n) / sum(n) AS top_cat_share, count() AS ncat, any(sessions) AS sessions, any(devices) AS devices, any(regions) AS regions, any(buys) AS buys
      FROM (SELECT user_id::String AS u, c.category::String AS cat, countIf(event_type::String = 'view') AS n FROM shop.history_events e JOIN shop.catalog c ON c.product_id::String = e.product_id::String GROUP BY u, cat) a
      JOIN (SELECT user_id::String AS u, uniqExact(session_id::String) AS sessions, uniqExact(device::String) AS devices, uniqExact(region::String) AS regions, countIf(event_type::String = 'purchase') AS buys FROM shop.history_events GROUP BY u) b USING u
      GROUP BY u);

-- funnel: is a purchase always preceded by view and add_to_cart of the same product in the session
SELECT count() AS session_products, countIf(buys > 0) AS bought, countIf(buys > 0 AND carts = 0) AS bought_without_cart, countIf(buys > 0 AND views = 0) AS bought_without_view, countIf(buys > 1) AS bought_twice_in_session,
       round(countIf(carts > 0) / count(), 4) AS cart_per_viewed_product, round(countIf(buys > 0) / countIf(carts > 0), 3) AS buy_given_cart
FROM (SELECT session_id::String AS s, product_id::String AS p, countIf(event_type::String = 'view') AS views, countIf(event_type::String = 'add_to_cart') AS carts, countIf(event_type::String = 'purchase') AS buys FROM shop.history_events GROUP BY s, p);

-- repeat purchases of the same product by the same user
SELECT count() AS user_products_bought, countIf(n > 1) AS bought_more_than_once, countIf(days > 1) AS on_different_days, max(n) AS mx
FROM (SELECT user_id::String AS u, product_id::String AS p, count() AS n, uniqExact(toDate(ts::DateTime64(3))) AS days FROM shop.history_events WHERE event_type::String = 'purchase' GROUP BY u, p);

-- consecutive views in a session: how similar is the next product
SELECT count() AS pairs, round(avg(p = pp), 3) AS same_product, round(avg(sub = psub), 3) AS same_subcategory, round(avg(brand = pbrand), 3) AS same_brand, round(avg(cat = pcat), 3) AS same_category
FROM (SELECT s, p, sub, brand, cat, lagInFrame(p) OVER w AS pp, lagInFrame(sub) OVER w AS psub, lagInFrame(brand) OVER w AS pbrand, lagInFrame(cat) OVER w AS pcat, row_number() OVER w AS rn
      FROM (SELECT e.session_id::String AS s, e.ts::DateTime64(3) AS t, e.product_id::String AS p, c.subcategory::String AS sub, c.brand::String AS brand, c.category::String AS cat
            FROM shop.history_events e JOIN shop.catalog c ON c.product_id::String = e.product_id::String WHERE e.event_type::String = 'view' AND e.ts::DateTime64(3) >= '2026-11-01')
      WINDOW w AS (PARTITION BY s ORDER BY t))
WHERE rn > 1;

-- purchases and views by category
SELECT c.category::String AS category, countIf(event_type::String = 'view') AS views, countIf(event_type::String = 'purchase') AS buys, round(100 * buys / views, 2) AS buy_per_view, round(avgIf(e.price_eur::Float64, event_type::String = 'purchase'), 2) AS avg_price_bought,
       round(avgIf(e.price_eur::Float64, event_type::String = 'view'), 2) AS avg_price_viewed
FROM shop.history_events e JOIN shop.catalog c ON c.product_id::String = e.product_id::String GROUP BY category ORDER BY views DESC;

-- did prices change during history
SELECT count() AS products, countIf(prices > 1) AS with_price_change, max(prices) AS max_prices, countIf(abs(last_price - cat_price) > 0.001) AS last_differs_from_catalog
FROM (SELECT e.product_id::String AS p, uniqExact(e.price_eur::Float64) AS prices, argMax(e.price_eur::Float64, e.ts::DateTime64(3)) AS last_price, any(c.price_eur::Float64) AS cat_price
      FROM shop.history_events e JOIN shop.catalog c ON c.product_id::String = e.product_id::String GROUP BY p);

-- trends: weekly views per product, how peaked (max week / median week), products with >= 500 views
SELECT count() AS products, quantilesExact(0.5, 0.9, 0.99)(round(peak, 2)) AS peak_ratio_q, countIf(peak > 3) AS peak_over_3x, countIf(peak > 10) AS peak_over_10x
FROM (SELECT p, max(n) / quantileExact(0.5)(n) AS peak, sum(n) AS total FROM (SELECT product_id::String AS p, toStartOfWeek(ts::DateTime64(3)) AS w, count() AS n FROM shop.history_events WHERE event_type::String = 'view' GROUP BY p, w) GROUP BY p HAVING total >= 500);

-- product first appearance in events vs catalogue created_at
SELECT toStartOfWeek(first_seen) AS week, count() AS products_first_seen, countIf(created >= '2026-09-01') AS created_since_sep
FROM (SELECT e.product_id::String AS p, min(e.ts::DateTime64(3)) AS first_seen, any(c.created_at::DateTime64(3)) AS created FROM shop.history_events e JOIN shop.catalog c ON c.product_id::String = e.product_id::String GROUP BY p)
GROUP BY week ORDER BY week;

-- events per day and type (every 6th day)
SELECT toDate(ts::DateTime64(3)) AS d, countIf(event_type::String = 'view') AS views, countIf(event_type::String = 'add_to_cart') AS carts, countIf(event_type::String = 'purchase') AS buys, uniqExact(user_id::String) AS users, uniqExact(product_id::String) AS products
FROM shop.history_events GROUP BY d HAVING toDayOfYear(d) % 6 = 0 ORDER BY d;

-- concentration of purchases over products
SELECT count() AS products, sum(n) AS purchases, round(100 * sumIf(n, r <= 10) / purchases, 1) AS top10_pct, round(100 * sumIf(n, r <= 100) / purchases, 1) AS top100_pct, round(100 * sumIf(n, r <= 1000) / purchases, 1) AS top1000_pct
FROM (SELECT p, n, row_number() OVER (ORDER BY n DESC) AS r FROM (SELECT product_id::String AS p, count() AS n FROM shop.history_events WHERE event_type::String = 'purchase' GROUP BY p))
