-- Carousel history (shop.history_sessions, 2M impressions of 10 slots, old "best sellers + noise" policy).

-- base rates by page
SELECT context.page::String AS page, count() AS n, round(100 * countIf(isNotNull(clicked)) / n, 2) AS ctr, round(100 * countIf(isNotNull(purchased)) / n, 2) AS conv,
       round(100 * countIf(isNotNull(purchased)) / countIf(isNotNull(clicked)), 1) AS buy_given_click, round(sum(revenue_eur::Float64) / n, 3) AS eur_per_req,
       round(avg(length(recent_views)), 2) AS avg_views
FROM shop.history_sessions GROUP BY page ORDER BY n DESC;

-- by number of recent views
SELECT length(recent_views) AS views, count() AS n, round(100 * countIf(isNotNull(clicked)) / n, 2) AS ctr, round(100 * countIf(isNotNull(purchased)) / n, 2) AS conv
FROM shop.history_sessions GROUP BY views ORDER BY views;

-- propensity by slot
SELECT k AS slot, round(avg(p), 4) AS mean_p, quantilesExact(0.01, 0.1, 0.5, 0.9, 0.99)(p) AS q, min(p) AS min_p, max(p) AS max_p
FROM (SELECT arrayJoin(arrayEnumerate(propensity::Array(Float64))) AS k, (propensity::Array(Float64))[k] AS p FROM shop.history_sessions WHERE ts::DateTime64(3) >= '2026-11-10')
GROUP BY k ORDER BY k;

-- how concentrated are impressions
SELECT count() AS products_shown, sum(n) AS impressions, round(100 * sumIf(n, r <= 10) / impressions, 1) AS top10_pct, round(100 * sumIf(n, r <= 50) / impressions, 1) AS top50_pct,
       round(100 * sumIf(n, r <= 200) / impressions, 1) AS top200_pct, round(100 * sumIf(n, r <= 1000) / impressions, 1) AS top1000_pct, min(n) AS min_n, quantileExact(0.5)(n) AS median_n
FROM (SELECT p, n, row_number() OVER (ORDER BY n DESC) AS r FROM (SELECT arrayJoin(shown::Array(String)) AS p, count() AS n FROM shop.history_sessions GROUP BY p));

-- is the old policy personalised: propensity of the top product in slot 1
SELECT toDate(ts::DateTime64(3)) AS d, count() AS n, uniqExact(round(p, 6)) AS distinct_p, round(min(p), 4) AS min_p, round(max(p), 4) AS max_p
FROM (SELECT ts, (propensity::Array(Float64))[1] AS p FROM shop.history_sessions WHERE (shown::Array(String))[1] = 'p_adc3e6')
GROUP BY d ORDER BY d LIMIT 8;

-- slot effect for one fixed product (the most shown), all pages
SELECT k AS slot, count() AS shown_n, round(100 * countIf(clicked::String = 'p_adc3e6') / shown_n, 3) AS ctr, round(100 * countIf(purchased::String = 'p_adc3e6') / shown_n, 3) AS conv
FROM (SELECT clicked, purchased, indexOf(shown::Array(String), 'p_adc3e6') AS k FROM shop.history_sessions WHERE has(shown::Array(String), 'p_adc3e6'))
GROUP BY k ORDER BY k;

-- slot effect, all products pooled
SELECT k AS slot, count() AS shown_n, round(100 * countIf(ck = sh[k]) / shown_n, 3) AS ctr, round(100 * countIf(pu = sh[k]) / shown_n, 3) AS conv, round(100 * countIf(pu = sh[k]) / countIf(ck = sh[k]), 1) AS buy_given_click
FROM (SELECT shown::Array(String) AS sh, ifNull(clicked::String, '') AS ck, ifNull(purchased::String, '') AS pu, arrayJoin(range(1, 11)) AS k FROM shop.history_sessions)
GROUP BY k ORDER BY k;

-- conversion by day (every 4th day)
SELECT toDate(ts::DateTime64(3)) AS d, count() AS n, round(100 * countIf(isNotNull(clicked)) / n, 2) AS ctr, round(100 * countIf(isNotNull(purchased)) / n, 2) AS conv, uniqExact(user_id::String) AS users
FROM shop.history_sessions GROUP BY d HAVING toDayOfYear(d) % 4 = 0 ORDER BY d;

-- conversion by hour of day (UTC)
SELECT toHour(ts::DateTime64(3)) AS h, count() AS n, round(100 * countIf(isNotNull(clicked)) / n, 2) AS ctr, round(100 * countIf(isNotNull(purchased)) / n, 2) AS conv
FROM shop.history_sessions GROUP BY h ORDER BY h;

-- clicks per request and purchase equals click
SELECT countIf(isNotNull(clicked)) AS clicks, countIf(isNotNull(purchased)) AS purchases, countIf(isNotNull(purchased) AND purchased::String != clicked::String) AS bought_other,
       countIf(isNotNull(clicked) AND NOT has(shown::Array(String), clicked::String)) AS clicked_not_shown, countIf(length(shown::Array(String)) != 10) AS not_ten,
       countIf(length(arrayDistinct(shown::Array(String))) != 10) AS dup_lists, round(avg(revenue_eur::Float64 > 0), 4) AS rev_share
FROM shop.history_sessions
