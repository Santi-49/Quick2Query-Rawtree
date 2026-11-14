-- Rebuy and revisit, with unmatched left-join rows handled (they come back as 1970 or 0, not NULL).

-- shown product (slots 1-3, non-home, last 20 days) bought before by the same user
SELECT multiIf(b.first_buy < '2000-01-01', '0 never bought', b.first_buy >= x.t - INTERVAL 1 HOUR, '9 bought now or later', in_rv, '1 bought before, in recent views', '2 bought before, not in recent views') AS state, count() AS shown_n,
       round(100 * countIf(ck = sp) / shown_n, 2) AS ctr, round(100 * countIf(pu = sp) / shown_n, 2) AS conv, round(100 * countIf(pu = sp) / countIf(ck = sp), 1) AS buy_given_click
FROM (SELECT user_id::String AS u, ts::DateTime64(3) AS t, sh[k] AS sp, ck, pu, has(rv, sh[k]) AS in_rv
      FROM (SELECT user_id, ts, shown::Array(String) AS sh, ifNull(clicked::String, '') AS ck, ifNull(purchased::String, '') AS pu, arrayMap(v -> v.product_id::String, recent_views::Array(JSON)) AS rv, arrayJoin([1, 2, 3]) AS k
            FROM shop.history_sessions WHERE context.page::String != 'home' AND ts::DateTime64(3) >= '2026-10-25')) x
LEFT JOIN (SELECT user_id::String AS u, product_id::String AS sp, min(ts::DateTime64(3)) AS first_buy FROM shop.history_events WHERE event_type::String = 'purchase' GROUP BY u, sp) b USING (u, sp)
GROUP BY state ORDER BY state;

-- shown product (slots 1-3, non-home, last 10 days) by number of views in earlier days
SELECT multiIf(in_rv, '1 in recent views', v.n = 0, '2 never viewed before', v.n < 3, '3 viewed 1-2 times before', v.n < 10, '4 viewed 3-9 times', '5 viewed 10+ times') AS state, count() AS shown_n,
       round(100 * countIf(ck = sp) / shown_n, 2) AS ctr, round(100 * countIf(pu = sp) / shown_n, 2) AS conv
FROM (SELECT user_id::String AS u, sh[k] AS sp, ck, pu, has(rv, sh[k]) AS in_rv
      FROM (SELECT user_id, shown::Array(String) AS sh, ifNull(clicked::String, '') AS ck, ifNull(purchased::String, '') AS pu, arrayMap(v -> v.product_id::String, recent_views::Array(JSON)) AS rv, arrayJoin([1, 2, 3]) AS k
            FROM shop.history_sessions WHERE context.page::String != 'home' AND ts::DateTime64(3) >= '2026-11-04')) x
LEFT JOIN (SELECT user_id::String AS u, product_id::String AS sp, count() AS n FROM shop.history_events WHERE event_type::String = 'view' AND ts::DateTime64(3) < '2026-11-04' GROUP BY u, sp) v USING (u, sp)
GROUP BY state ORDER BY state;

-- organic: after buying a product, does the user view or buy it again later (pairs first bought before 15 Oct)
SELECT count() AS pairs, round(avg(later_views > 0), 3) AS viewed_again, round(avg(later_buys > 0), 3) AS bought_again
FROM (SELECT u, p, countIf(et = 'view' AND t > fb + INTERVAL 1 DAY) AS later_views, countIf(et = 'purchase' AND t > fb + INTERVAL 1 DAY) AS later_buys
      FROM (SELECT user_id::String AS u, product_id::String AS p, event_type::String AS et, ts::DateTime64(3) AS t FROM shop.history_events) e
      JOIN (SELECT user_id::String AS u, product_id::String AS p, min(ts::DateTime64(3)) AS fb FROM shop.history_events WHERE event_type::String = 'purchase' GROUP BY u, p HAVING fb < '2026-10-15') b USING (u, p)
      GROUP BY u, p);

-- organic, for comparison: products viewed but not bought before 15 Oct, viewed or bought after
SELECT count() AS pairs, round(avg(later_views > 0), 3) AS viewed_again, round(avg(later_buys > 0), 3) AS bought_later
FROM (SELECT user_id::String AS u, product_id::String AS p, countIf(event_type::String = 'view' AND ts::DateTime64(3) < '2026-10-15') AS early_views, countIf(event_type::String = 'purchase' AND ts::DateTime64(3) < '2026-10-15') AS early_buys,
             countIf(event_type::String = 'view' AND ts::DateTime64(3) >= '2026-10-16') AS later_views, countIf(event_type::String = 'purchase' AND ts::DateTime64(3) >= '2026-10-16') AS later_buys
      FROM shop.history_events GROUP BY u, p HAVING early_views > 0 AND early_buys = 0)
