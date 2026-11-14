-- H-home-best-list: slot-weighted purchase rate of impression classes on history home requests, as a proxy for simple home policies.
-- Home requests from 15 Oct 07:00; shopper profile and best-seller ranks from organic history before that date. wconv = purchases / sum of 1/log2(slot+1).

-- impression classes on history home requests (last 30 days, profile and best-seller ranks from the first 30 days)
WITH imp AS (SELECT u, sh[k] AS sp, k, 1 / log2(k + 1) AS w, ck, pu
             FROM (SELECT user_id::String AS u, shown::Array(String) AS sh, ifNull(clicked::String, '') AS ck, ifNull(purchased::String, '') AS pu, arrayJoin(range(1, 11)) AS k
                   FROM shop.history_sessions WHERE context.page::String = 'home' AND ts::DateTime64(3) >= '2026-10-15 07:00:00')),
     ev AS (SELECT e.user_id::String AS u, e.product_id::String AS p, e.event_type::String AS et, c.category::String AS cat, c.subcategory::String AS sub
            FROM shop.history_events e JOIN shop.catalog c ON c.product_id::String = e.product_id::String WHERE e.ts::DateTime64(3) < '2026-10-15 07:00:00'),
     bs AS (SELECT p, row_number() OVER (PARTITION BY cat ORDER BY nb DESC, p) AS r FROM (SELECT p, any(cat) AS cat, countIf(et = 'purchase') AS nb FROM ev GROUP BY p)),
     up AS (SELECT u, p, countIf(et = 'view') AS nv, countIf(et = 'purchase') AS nb FROM ev WHERE p IN (SELECT DISTINCT sp FROM imp) GROUP BY u, p),
     vr AS (SELECT u, p, row_number() OVER (PARTITION BY u, cat ORDER BY nv DESC, p) AS r FROM (SELECT u, p, any(cat) AS cat, countIf(et = 'view') AS nv, countIf(et = 'purchase') AS nb FROM ev GROUP BY u, p HAVING nb = 0 AND nv > 0)),
     ts AS (SELECT u, cat, argMax(sub, n) AS top_sub FROM (SELECT u, cat, sub, count() AS n FROM ev WHERE et = 'view' GROUP BY u, cat, sub) GROUP BY u, cat)
SELECT multiIf(up.nb > 0, 'A bought before', vr.r BETWEEN 1 AND 3, 'B viewed not bought, top 3 in cat', vr.r > 3, 'C viewed not bought, rank 4+ in cat',
               ts.top_sub = c.subcategory::String AND bs.r <= 30, 'D top sub, best seller 1-30', ts.top_sub = c.subcategory::String, 'E top sub, other',
               bs.r <= 10, 'F best seller 1-10 of cat', bs.r <= 30, 'G best seller 11-30', 'H other') AS class,
       count() AS n, round(sum(w)) AS wsum, countIf(ck = imp.sp) AS clicks, countIf(pu = imp.sp) AS buys, round(100 * clicks / wsum, 3) AS wctr, round(100 * buys / wsum, 4) AS wconv
FROM imp JOIN shop.catalog c ON c.product_id::String = imp.sp
LEFT JOIN bs ON bs.p = imp.sp LEFT JOIN up ON up.u = imp.u AND up.p = imp.sp LEFT JOIN vr ON vr.u = imp.u AND vr.p = imp.sp
LEFT JOIN ts ON ts.u = imp.u AND ts.cat = c.category::String
GROUP BY class ORDER BY class;

-- coverage: home requests by number of viewed-not-bought products the shopper has in the shown category, and whether the shown category is the shopper's top
WITH req AS (SELECT x.u AS u, c.category::String AS cat FROM (SELECT user_id::String AS u, (shown::Array(String))[1] AS s1 FROM shop.history_sessions WHERE context.page::String = 'home' AND ts::DateTime64(3) >= '2026-10-15 07:00:00') x
             JOIN shop.catalog c ON c.product_id::String = x.s1),
     ev AS (SELECT e.user_id::String AS u, e.product_id::String AS p, e.event_type::String AS et, c.category::String AS cat FROM shop.history_events e JOIN shop.catalog c ON c.product_id::String = e.product_id::String WHERE e.ts::DateTime64(3) < '2026-10-15 07:00:00'),
     vc AS (SELECT u, cat, count() AS nvp FROM (SELECT u, p, any(cat) AS cat FROM ev GROUP BY u, p HAVING countIf(et = 'purchase') = 0 AND countIf(et = 'view') > 0) GROUP BY u, cat)
SELECT multiIf(vc.nvp = 0, '0', vc.nvp < 3, '1-2', vc.nvp < 10, '3-9', '10+') AS viewed_not_bought_in_cat, count() AS requests, round(count() / (SELECT count() FROM req), 3) AS share
FROM req LEFT JOIN vc ON vc.u = req.u AND vc.cat = req.cat GROUP BY viewed_not_bought_in_cat ORDER BY viewed_not_bought_in_cat;

-- coverage: viewed-not-bought products per returning shopper overall and in their top category (profile = all history)
WITH ev AS (SELECT e.user_id::String AS u, e.product_id::String AS p, e.event_type::String AS et, c.category::String AS cat FROM shop.history_events e JOIN shop.catalog c ON c.product_id::String = e.product_id::String),
     vp AS (SELECT u, p, any(cat) AS cat FROM ev GROUP BY u, p HAVING countIf(et = 'purchase') = 0 AND countIf(et = 'view') > 0),
     top AS (SELECT u, argMax(cat, n) AS tc FROM (SELECT u, cat, countIf(et = 'view') AS n FROM ev GROUP BY u, cat) GROUP BY u)
SELECT count() AS users, quantiles(0.1, 0.5, 0.9)(n_all) AS viewed_not_bought_all, quantiles(0.1, 0.5, 0.9)(n_top) AS viewed_not_bought_top_cat, round(countIf(n_top >= 10) / users, 3) AS share_10plus_in_top
FROM (SELECT vp.u AS u, count() AS n_all, countIf(vp.cat = top.tc) AS n_top FROM vp JOIN top ON top.u = vp.u GROUP BY vp.u);

-- category rank x product class, history home (last 30 days, profile from first 30)
WITH imp AS (SELECT u, sh[k] AS sp, k, 1 / log2(k + 1) AS w, ck, pu
             FROM (SELECT user_id::String AS u, shown::Array(String) AS sh, ifNull(clicked::String, '') AS ck, ifNull(purchased::String, '') AS pu, arrayJoin(range(1, 11)) AS k
                   FROM shop.history_sessions WHERE context.page::String = 'home' AND ts::DateTime64(3) >= '2026-10-15 07:00:00')),
     ev AS (SELECT e.user_id::String AS u, e.product_id::String AS p, e.event_type::String AS et, c.category::String AS cat
            FROM shop.history_events e JOIN shop.catalog c ON c.product_id::String = e.product_id::String WHERE e.ts::DateTime64(3) < '2026-10-15 07:00:00'),
     bs AS (SELECT p, row_number() OVER (PARTITION BY cat ORDER BY nb DESC, p) AS r FROM (SELECT p, any(cat) AS cat, countIf(et = 'purchase') AS nb FROM ev GROUP BY p)),
     up AS (SELECT u, p, countIf(et = 'view') AS nv, countIf(et = 'purchase') AS nb FROM ev WHERE p IN (SELECT DISTINCT sp FROM imp) GROUP BY u, p),
     rk AS (SELECT u, cat, row_number() OVER (PARTITION BY u ORDER BY n DESC, cat) AS rc FROM (SELECT u, cat, countIf(et = 'view') AS n FROM ev GROUP BY u, cat))
SELECT multiIf(rk.rc = 1, '1 top cat', rk.rc IN (2, 3), '2 cat 2-3', '3 other cat') AS cat_rank,
       multiIf(up.nb > 0, 'A bought before', up.nv > 0, 'B viewed not bought', bs.r <= 10, 'C best seller 1-10', 'D other') AS class,
       count() AS n, round(sum(w)) AS wsum, countIf(ck = imp.sp) AS clicks, countIf(pu = imp.sp) AS buys, round(100 * clicks / wsum, 3) AS wctr, round(100 * buys / wsum, 4) AS wconv
FROM imp JOIN shop.catalog c ON c.product_id::String = imp.sp
LEFT JOIN bs ON bs.p = imp.sp LEFT JOIN up ON up.u = imp.u AND up.p = imp.sp LEFT JOIN rk ON rk.u = imp.u AND rk.cat = c.category::String
GROUP BY cat_rank, class ORDER BY cat_rank, class;
