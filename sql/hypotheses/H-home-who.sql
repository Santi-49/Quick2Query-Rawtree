-- H-home-who · aggregates in RawTree that back docs/hypotheses/H-home-who.md. Read-only.
-- uv run scripts/q.py sql/hypotheses/H-home-who.sql [title]
-- The per-request work (generators, list features) is in eda/home/*.py on the pull of eda/home/pull.py.

-- 1 home equals no recent views: page x no-views x new shopper
SELECT context.page::String AS page, length(recent_views::Array(JSON)) = 0 AS no_views, is_new_user::Bool AS new, count() AS n
FROM shop.requests GROUP BY page, no_views, new ORDER BY n DESC;

-- 2 requests and events are separate streams: share of requests' last recent view found in shop.events (1/20 sample)
WITH rv AS (SELECT user_id::String AS u, (recent_views::Array(JSON))[-1].product_id::String AS p FROM shop.requests
            WHERE length(recent_views::Array(JSON)) > 0 AND cityHash64(request_id::String) % 20 = 0)
SELECT count() AS n, countIf(e.n > 0) AS last_view_in_events, round(100 * countIf(e.n > 0) / count(), 1) AS pct
FROM rv LEFT JOIN (SELECT user_id::String AS u, product_id::String AS p, count() AS n FROM shop.events
                   WHERE event_type::String = 'view' GROUP BY u, p) e ON e.u = rv.u AND e.p = rv.p;

-- 3 list conversion and click, home vs with views, by shopper class (history / events earlier today / unknown), our answers only
WITH r AS (SELECT request_id::String AS rid, any(user_id::String) AS u, any(length(recent_views::Array(JSON)) = 0) AS home,
                  any(toUnixTimestamp64Milli(ts::DateTime64(3, 'UTC')) / 1000) AS t FROM shop.requests GROUP BY rid),
     f AS (SELECT request_id::String AS rid, any(purchased::String) != '' AS buy, any(clicked::String) != '' AS clk
           FROM {TEAM}.feedback WHERE served_by::String = 'team' GROUP BY rid),
     h AS (SELECT DISTINCT user_id::String AS u FROM shop.history_events),
     e AS (SELECT user_id::String AS u, min(toUnixTimestamp64Milli(ts::DateTime64(3, 'UTC')) / 1000) AS first_t FROM shop.events GROUP BY u)
SELECT r.home AS home, multiIf(h.u != '', '1 history', e.first_t > 0 AND e.first_t < r.t, '2 today only', '3 unknown') AS shopper,
       count() AS n, round(100 * avg(f.buy), 2) AS conv, round(100 * sqrt(avg(f.buy) * (1 - avg(f.buy)) / count()), 2) AS se, sum(f.buy) AS buys,
       round(100 * avg(f.clk), 2) AS click
FROM r INNER JOIN f ON f.rid = r.rid LEFT JOIN h ON h.u = r.u LEFT JOIN e ON e.u = r.u
GROUP BY home, shopper ORDER BY home, shopper;

-- 4 organic purchase by the same shopper in the 30 min after the request, home vs with views (complete windows)
WITH r AS (SELECT request_id::String AS rid, any(user_id::String) AS u, any(length(recent_views::Array(JSON)) = 0) AS home,
                  any(toUnixTimestamp64Milli(ts::DateTime64(3, 'UTC')) / 1000) AS t FROM shop.requests GROUP BY rid
           HAVING t < (SELECT toUnixTimestamp64Milli(max(ts::DateTime64(3, 'UTC'))) / 1000 - 1800 FROM shop.events)),
     b AS (SELECT user_id::String AS u, toUnixTimestamp64Milli(ts::DateTime64(3, 'UTC')) / 1000 AS bt FROM shop.events WHERE event_type::String = 'purchase'),
     x AS (SELECT r.rid AS rid, any(r.home) AS home, countIf(b.bt >= r.t AND b.bt < r.t + 1800) > 0 AS o30 FROM r LEFT JOIN b ON b.u = r.u GROUP BY r.rid)
SELECT home, count() AS n, round(100 * avg(o30), 2) AS organic_buy_30min, round(100 * sqrt(avg(o30) * (1 - avg(o30)) / count()), 2) AS se
FROM x GROUP BY home;

-- 5 home conversion by device x region segment and new shopper, our answers only
WITH r AS (SELECT request_id::String AS rid, any(is_new_user::Bool) AS new,
                  any(context.device::String = 'android' AND context.region::String IN ('Andalucía', 'Canarias', 'Murcia')) AS south
           FROM shop.requests WHERE length(recent_views::Array(JSON)) = 0 GROUP BY rid),
     f AS (SELECT request_id::String AS rid, any(purchased::String) != '' AS buy, any(clicked::String) != '' AS clk
           FROM {TEAM}.feedback WHERE served_by::String = 'team' GROUP BY rid)
SELECT new, south, count() AS n, round(100 * avg(buy), 2) AS conv, round(100 * sqrt(avg(buy) * (1 - avg(buy)) / count()), 2) AS se, sum(buy) AS buys,
       round(100 * avg(clk), 2) AS click
FROM r INNER JOIN f ON f.rid = r.rid GROUP BY new, south ORDER BY new, south;
