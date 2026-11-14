-- Carousel history, part 3. Fact used throughout: the old policy only ever showed products of ONE category per request.

-- requests and conversion by shown category (non-home)
SELECT c.category::String AS category, count() AS n, round(100 * countIf(isNotNull(x.clicked)) / n, 2) AS ctr, round(100 * countIf(isNotNull(x.purchased)) / n, 2) AS conv, round(avg(x.rev), 3) AS eur_per_req
FROM (SELECT (shown::Array(String))[1] AS sp, clicked, purchased, revenue_eur::Float64 AS rev FROM shop.history_sessions WHERE context.page::String != 'home') x
JOIN shop.catalog c ON c.product_id::String = x.sp GROUP BY category ORDER BY n DESC;

-- home page: shown category
SELECT c.category::String AS category, count() AS n, round(100 * countIf(isNotNull(x.clicked)) / n, 2) AS ctr, round(100 * countIf(isNotNull(x.purchased)) / n, 2) AS conv
FROM (SELECT (shown::Array(String))[1] AS sp, clicked, purchased FROM shop.history_sessions WHERE context.page::String = 'home') x
JOIN shop.catalog c ON c.product_id::String = x.sp GROUP BY category ORDER BY n DESC;

-- shown product is one of the recent views: by how recent (1 = last view), slots 1-3
SELECT pos_from_end, count() AS shown_n, round(100 * countIf(ck = sp) / shown_n, 2) AS ctr, round(100 * countIf(pu = sp) / shown_n, 2) AS conv, round(100 * countIf(pu = sp) / countIf(ck = sp), 1) AS buy_given_click
FROM (SELECT sh[k] AS sp, ck, pu, if(indexOf(arrayReverse(rv), sh[k]) = 0, 99, indexOf(arrayReverse(rv), sh[k])) AS pos_from_end
      FROM (SELECT shown::Array(String) AS sh, ifNull(clicked::String, '') AS ck, ifNull(purchased::String, '') AS pu, arrayMap(v -> v.product_id::String, recent_views::Array(JSON)) AS rv, arrayJoin([1, 2, 3]) AS k
            FROM shop.history_sessions WHERE context.page::String != 'home'))
GROUP BY pos_from_end ORDER BY pos_from_end;

-- shown product viewed n times within recent views, slots 1-3
SELECT times_viewed, count() AS shown_n, round(100 * countIf(ck = sp) / shown_n, 2) AS ctr, round(100 * countIf(pu = sp) / shown_n, 2) AS conv
FROM (SELECT sh[k] AS sp, ck, pu, countEqual(rv, sh[k]) AS times_viewed
      FROM (SELECT shown::Array(String) AS sh, ifNull(clicked::String, '') AS ck, ifNull(purchased::String, '') AS pu, arrayMap(v -> v.product_id::String, recent_views::Array(JSON)) AS rv, arrayJoin([1, 2, 3]) AS k
            FROM shop.history_sessions WHERE context.page::String != 'home'))
GROUP BY times_viewed ORDER BY times_viewed;

-- price band, slot 1, product not in recent views
SELECT multiIf(price < 10, '0-10', price < 20, '10-20', price < 35, '20-35', price < 60, '35-60', price < 120, '60-120', '120+') AS band, count() AS shown_n,
       round(100 * countIf(ck = sp) / shown_n, 2) AS ctr, round(100 * countIf(pu = sp) / countIf(ck = sp), 1) AS buy_given_click, round(100 * countIf(pu = sp) / shown_n, 3) AS conv, round(sum(if(pu = sp, price, 0)) / shown_n, 3) AS eur_per_show
FROM (SELECT (shown::Array(String))[1] AS sp, ifNull(clicked::String, '') AS ck, ifNull(purchased::String, '') AS pu
      FROM shop.history_sessions WHERE context.page::String != 'home' AND NOT has(arrayMap(v -> v.product_id::String, recent_views::Array(JSON)), (shown::Array(String))[1])) x
JOIN (SELECT product_id::String AS pid, price_eur::Float64 AS price FROM shop.catalog) c ON c.pid = x.sp
GROUP BY band ORDER BY min(price);

-- price relative to the last viewed product, slot 1, product not in recent views
SELECT multiIf(ratio < 0.5, '1 <0.5x', ratio < 0.8, '2 0.5-0.8x', ratio < 1.25, '3 0.8-1.25x', ratio < 2, '4 1.25-2x', '5 >2x') AS rel_price, count() AS shown_n,
       round(100 * countIf(ck = sp) / shown_n, 2) AS ctr, round(100 * countIf(pu = sp) / countIf(ck = sp), 1) AS buy_given_click, round(100 * countIf(pu = sp) / shown_n, 3) AS conv
FROM (SELECT sp, ck, pu, c.price / l.lp AS ratio
      FROM (SELECT (shown::Array(String))[1] AS sp, ifNull(clicked::String, '') AS ck, ifNull(purchased::String, '') AS pu, (recent_views::Array(JSON))[-1].product_id::String AS lv
            FROM shop.history_sessions WHERE context.page::String != 'home' AND NOT has(arrayMap(v -> v.product_id::String, recent_views::Array(JSON)), (shown::Array(String))[1])) x
      JOIN (SELECT product_id::String AS pid, price_eur::Float64 AS price FROM shop.catalog) c ON c.pid = x.sp
      JOIN (SELECT product_id::String AS pid2, price_eur::Float64 AS lp FROM shop.catalog) l ON l.pid2 = x.lv)
GROUP BY rel_price ORDER BY rel_price;

-- product appeal: slot-1 click rate spread across products with at least 2000 slot-1 impressions (non-home)
SELECT count() AS products, round(quantileExact(0.05)(ctr), 2) AS p05, round(quantileExact(0.25)(ctr), 2) AS p25, round(quantileExact(0.5)(ctr), 2) AS p50, round(quantileExact(0.75)(ctr), 2) AS p75, round(quantileExact(0.95)(ctr), 2) AS p95, round(max(ctr), 2) AS mx
FROM (SELECT (shown::Array(String))[1] AS sp, count() AS n, 100 * countIf(clicked::String = sp) / n AS ctr FROM shop.history_sessions WHERE context.page::String != 'home' GROUP BY sp HAVING n >= 2000);

-- propensity vs product appeal: is the most shown product the most clicked at slot 1 (top 12 by impressions in Electronics)
SELECT sp, count() AS n, round(avg(p), 3) AS prop, round(100 * countIf(clicked::String = sp) / n, 2) AS ctr, round(100 * countIf(purchased::String = sp) / n, 2) AS conv
FROM (SELECT (shown::Array(String))[1] AS sp, (propensity::Array(Float64))[1] AS p, clicked, purchased FROM shop.history_sessions WHERE context.page::String != 'home')
GROUP BY sp ORDER BY n DESC LIMIT 12;

-- device x region conversion (non-home)
SELECT context.region::String AS region, count() AS n, round(100 * countIf(isNotNull(clicked)) / n, 2) AS ctr, round(100 * countIf(isNotNull(purchased)) / n, 2) AS conv,
       round(100 * countIf(isNotNull(purchased) AND context.device::String = 'android') / countIf(context.device::String = 'android'), 2) AS conv_android,
       round(100 * countIf(isNotNull(purchased) AND context.device::String = 'ios') / countIf(context.device::String = 'ios'), 2) AS conv_ios,
       round(100 * countIf(isNotNull(purchased) AND context.device::String = 'web') / countIf(context.device::String = 'web'), 2) AS conv_web
FROM shop.history_sessions WHERE context.page::String != 'home' GROUP BY region ORDER BY n DESC;

-- requests per user and per user-day
SELECT count() AS users, round(avg(n), 1) AS avg_requests, quantilesExact(0.1, 0.5, 0.9, 0.99)(n) AS q, max(n) AS mx, round(avg(buys), 2) AS avg_buys, round(avg(buys > 0), 3) AS share_buyers
FROM (SELECT user_id::String AS u, count() AS n, countIf(isNotNull(purchased)) AS buys FROM shop.history_sessions GROUP BY u)
