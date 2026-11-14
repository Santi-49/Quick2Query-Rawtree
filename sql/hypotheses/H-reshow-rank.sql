-- H-reshow-rank: among the recent views themselves, which should lead: the last one, the most repeated, the cheapest, the most popular?
-- Only impressions of a shown product that is one of the request's recent views. Slot-weighted, w = 1/log2(slot+1); ctr_w, conv_w per 100 weighted impressions.
-- Popularity = history purchases of the product (shop.history_events). Run: uv run scripts/q.py sql/hypotheses/H-reshow-rank.sql [title filter]

-- 1 live: re-shown recent view by number of views and position from the end (1 = last view)
WITH
fb AS (SELECT request_id::String AS rid, shown::Array(String) AS sh, clicked::String AS ck, purchased::String AS pu FROM {TEAM}.feedback WHERE length(shown::Array(String)) = 10),
rq AS (SELECT request_id::String AS rid, arrayMap(v -> v.product_id::String, recent_views::Array(JSON)) AS rv FROM shop.requests WHERE request_id::String IN (SELECT rid FROM fb) AND length(recent_views::Array(JSON)) > 0),
imp AS (SELECT rq.rv AS rv, fb.sh[k] AS sp, k, 1 / log2(k + 1) AS w, fb.ck = fb.sh[k] AS c, fb.pu = fb.sh[k] AS p FROM fb JOIN rq ON rq.rid = fb.rid ARRAY JOIN range(1, 11) AS k WHERE has(rq.rv, fb.sh[k]))
SELECT multiIf(length(rv) = 1, '1 view', length(rv) = 2, '2 views', length(rv) <= 4, '3-4 views', '5+ views') AS n_views,
       multiIf(sp = rv[-1], '1 last', sp = rv[-2], '2 2nd last', '3 3rd+ last') AS from_end,
       count() AS imps, round(avg(k), 1) AS avg_slot, round(sum(w)) AS w_imps, sum(c) AS clicks, sum(p) AS buys, round(100 * clicks / w_imps, 3) AS ctr_w, round(100 * buys / w_imps, 3) AS conv_w
FROM imp GROUP BY n_views, from_end ORDER BY n_views, from_end;

-- 2 history: re-shown recent view by number of views and position from the end
WITH
s AS (SELECT shown::Array(String) AS sh, arrayMap(v -> v.product_id::String, recent_views::Array(JSON)) AS rv, ifNull(clicked::Nullable(String), '') AS ck, ifNull(purchased::Nullable(String), '') AS pu
      FROM shop.history_sessions WHERE length(recent_views::Array(JSON)) > 0 AND hasAny(shown::Array(String), arrayMap(v -> v.product_id::String, recent_views::Array(JSON))))
SELECT multiIf(length(rv) = 1, '1 view', length(rv) = 2, '2 views', length(rv) <= 4, '3-4 views', '5+ views') AS n_views,
       multiIf(sh[k] = rv[-1], '1 last', sh[k] = rv[-2], '2 2nd last', '3 3rd+ last') AS from_end,
       count() AS imps, round(sum(1 / log2(k + 1))) AS w_imps, countIf(ck = sh[k]) AS clicks, countIf(pu = sh[k]) AS buys, round(100 * clicks / w_imps, 3) AS ctr_w, round(100 * buys / w_imps, 3) AS conv_w
FROM s ARRAY JOIN range(1, 11) AS k WHERE has(rv, sh[k]) GROUP BY n_views, from_end ORDER BY n_views, from_end;

-- 3 live, requests with 2+ distinct views: re-shown recent view by its rank among the views on price and on history purchases
WITH
prod AS (SELECT pid, any(price) AS price FROM (SELECT product_id::String AS pid, price_eur::Float64 AS price FROM shop.catalog UNION ALL SELECT product_id::String, price_eur::Float64 FROM shop.catalog_updates WHERE change::String = 'new_product') GROUP BY pid),
pop AS (SELECT product_id::String AS pid, count() AS buys FROM shop.history_events WHERE event_type::String = 'purchase' GROUP BY pid),
fb AS (SELECT request_id::String AS rid, shown::Array(String) AS sh, clicked::String AS ck, purchased::String AS pu FROM {TEAM}.feedback WHERE length(shown::Array(String)) = 10),
rq AS (SELECT request_id::String AS rid, arrayDistinct(arrayMap(v -> v.product_id::String, recent_views::Array(JSON))) AS dv FROM shop.requests WHERE request_id::String IN (SELECT rid FROM fb) AND length(arrayDistinct(arrayMap(v -> v.product_id::String, recent_views::Array(JSON)))) > 1),
vx AS (SELECT rid, min(p.price) AS minp, max(ifNull(o.buys, 0)) AS maxb FROM (SELECT rid, arrayJoin(dv) AS pid FROM rq) x JOIN prod p ON p.pid = x.pid LEFT JOIN pop o ON o.pid = x.pid GROUP BY rid),
imp AS (SELECT fb.rid AS rid, fb.sh[k] AS sp, 1 / log2(k + 1) AS w, fb.ck = fb.sh[k] AS c, fb.pu = fb.sh[k] AS p FROM fb JOIN rq ON rq.rid = fb.rid ARRAY JOIN range(1, 11) AS k WHERE has(rq.dv, fb.sh[k]))
SELECT 'price' AS rank_by, if(pr.price <= vx.minp, '1 cheapest view', '2 not cheapest') AS cell, count() AS imps, round(sum(w)) AS w_imps, sum(c) AS clicks, sum(p) AS buys, round(100 * clicks / w_imps, 3) AS ctr_w, round(100 * buys / w_imps, 3) AS conv_w
FROM imp JOIN prod pr ON pr.pid = imp.sp JOIN vx ON vx.rid = imp.rid GROUP BY cell
UNION ALL
SELECT 'history buys', if(ifNull(o.buys, 0) >= vx.maxb, '1 most bought view', '2 not most bought'), count(), round(sum(w)), sum(c), sum(p), round(100 * sum(c) / sum(w), 3), round(100 * sum(p) / sum(w), 3)
FROM imp LEFT JOIN pop o ON o.pid = imp.sp JOIN vx ON vx.rid = imp.rid GROUP BY 2
ORDER BY 1, 2;

-- 4 live, requests with 2+ views: is the last view in the subcategory of the earlier views? (re-shown last view against re-shown earlier views)
WITH
prod AS (SELECT pid, any(sub) AS sub FROM (SELECT product_id::String AS pid, subcategory::String AS sub FROM shop.catalog UNION ALL SELECT product_id::String, subcategory::String FROM shop.catalog_updates WHERE change::String = 'new_product') GROUP BY pid),
fb AS (SELECT request_id::String AS rid, shown::Array(String) AS sh, clicked::String AS ck, purchased::String AS pu FROM {TEAM}.feedback WHERE length(shown::Array(String)) = 10),
rq AS (SELECT request_id::String AS rid, arrayMap(v -> v.product_id::String, recent_views::Array(JSON)) AS rv FROM shop.requests WHERE request_id::String IN (SELECT rid FROM fb) AND length(recent_views::Array(JSON)) > 1),
vx AS (SELECT rid, arrayMap(x -> x.2, arraySort(groupArray((i, p.sub)))) AS vs FROM (SELECT rid, arrayJoin(arrayEnumerate(rv)) AS i, rv[i] AS pid FROM rq) x JOIN prod p ON p.pid = x.pid GROUP BY rid),
imp AS (SELECT rq.rv AS rv, vx.vs AS vs, fb.sh[k] AS sp, 1 / log2(k + 1) AS w, fb.ck = fb.sh[k] AS c, fb.pu = fb.sh[k] AS p
        FROM fb JOIN rq ON rq.rid = fb.rid JOIN vx ON vx.rid = fb.rid ARRAY JOIN range(1, 11) AS k WHERE length(vx.vs) = length(rq.rv) AND has(rq.rv, fb.sh[k]))
SELECT if(has(arrayPopBack(vs), vs[-1]), '1 last view in an earlier subcat', '2 last view in a new subcat') AS last_view, if(sp = rv[-1], '1 last', '2 earlier') AS shown,
       count() AS imps, round(sum(w)) AS w_imps, sum(c) AS clicks, sum(p) AS buys, round(100 * clicks / w_imps, 3) AS ctr_w, round(100 * buys / w_imps, 3) AS conv_w
FROM imp GROUP BY last_view, shown ORDER BY last_view, shown;

-- 5 live and history: re-shown recent view by position from the start (requests with 3+ views)
SELECT 'live' AS src, length(rq.rv) AS n, indexOf(rq.rv, fb.sh[k]) AS pos, round(sum(1 / log2(k + 1))) AS w_imps, countIf(fb.ck = fb.sh[k]) AS clicks, countIf(fb.pu = fb.sh[k]) AS buys, round(100 * clicks / w_imps, 2) AS ctr_w
FROM (SELECT request_id::String AS rid, shown::Array(String) AS sh, clicked::String AS ck, purchased::String AS pu FROM {TEAM}.feedback WHERE length(shown::Array(String)) = 10) fb
JOIN (SELECT request_id::String AS rid, arrayMap(v -> v.product_id::String, recent_views::Array(JSON)) AS rv FROM shop.requests WHERE length(recent_views::Array(JSON)) > 2) rq ON rq.rid = fb.rid
ARRAY JOIN range(1, 11) AS k WHERE has(rq.rv, fb.sh[k]) GROUP BY n, pos
UNION ALL
SELECT 'history', length(rv), indexOf(rv, sh[k]), round(sum(1 / log2(k + 1))), countIf(ck = sh[k]), countIf(pu = sh[k]), round(100 * countIf(ck = sh[k]) / sum(1 / log2(k + 1)), 2)
FROM (SELECT shown::Array(String) AS sh, arrayMap(v -> v.product_id::String, recent_views::Array(JSON)) AS rv, ifNull(clicked::Nullable(String), '') AS ck, ifNull(purchased::Nullable(String), '') AS pu
      FROM shop.history_sessions WHERE length(recent_views::Array(JSON)) > 2) ARRAY JOIN range(1, 11) AS k WHERE has(rv, sh[k]) GROUP BY 2, 3
ORDER BY 1, 2, 3;

-- 6 live: first view against later views, split by whether it is the most bought of the views (requests with 2+ distinct views)
WITH
pop AS (SELECT product_id::String AS pid, count() AS buys FROM shop.history_events WHERE event_type::String = 'purchase' GROUP BY pid),
fb AS (SELECT request_id::String AS rid, shown::Array(String) AS sh, clicked::String AS ck, purchased::String AS pu FROM {TEAM}.feedback WHERE length(shown::Array(String)) = 10),
rq AS (SELECT request_id::String AS rid, arrayMap(v -> v.product_id::String, recent_views::Array(JSON)) AS rv FROM shop.requests WHERE request_id::String IN (SELECT rid FROM fb) AND length(arrayDistinct(arrayMap(v -> v.product_id::String, recent_views::Array(JSON)))) > 1),
vx AS (SELECT rid, max(ifNull(o.buys, 0)) AS maxb FROM (SELECT rid, arrayJoin(rv) AS pid FROM rq) x LEFT JOIN pop o ON o.pid = x.pid GROUP BY rid),
imp AS (SELECT fb.rid AS rid, rq.rv AS rv, fb.sh[k] AS sp, 1 / log2(k + 1) AS w, fb.ck = fb.sh[k] AS c, fb.pu = fb.sh[k] AS p FROM fb JOIN rq ON rq.rid = fb.rid ARRAY JOIN range(1, 11) AS k WHERE has(rq.rv, fb.sh[k]))
SELECT if(sp = rv[1], '1 first view', '2 later view') AS position, if(ifNull(o.buys, 0) >= vx.maxb, '1 most bought', '2 not most bought') AS popularity,
       count() AS imps, round(sum(w)) AS w_imps, sum(c) AS clicks, sum(p) AS buys, round(100 * clicks / w_imps, 2) AS ctr_w, round(100 * buys / w_imps, 2) AS conv_w
FROM imp LEFT JOIN pop o ON o.pid = imp.sp JOIN vx ON vx.rid = imp.rid GROUP BY position, popularity ORDER BY position, popularity;

-- 7 history: first view against later views, split by whether it is the most bought of the views (requests with 2+ distinct views)
WITH
pop AS (SELECT product_id::String AS pid, count() AS buys FROM shop.history_events WHERE event_type::String = 'purchase' GROUP BY pid),
s AS (SELECT request_id::String AS rid, shown::Array(String) AS sh, arrayMap(v -> v.product_id::String, recent_views::Array(JSON)) AS rv, ifNull(clicked::Nullable(String), '') AS ck, ifNull(purchased::Nullable(String), '') AS pu
      FROM shop.history_sessions WHERE length(arrayDistinct(arrayMap(v -> v.product_id::String, recent_views::Array(JSON)))) > 1 AND hasAny(shown::Array(String), arrayMap(v -> v.product_id::String, recent_views::Array(JSON)))),
vx AS (SELECT rid, max(ifNull(o.buys, 0)) AS maxb FROM (SELECT rid, arrayJoin(rv) AS pid FROM s) x LEFT JOIN pop o ON o.pid = x.pid GROUP BY rid),
imp AS (SELECT s.rid AS rid, rv, sh[k] AS sp, 1 / log2(k + 1) AS w, ck = sh[k] AS c, pu = sh[k] AS p FROM s ARRAY JOIN range(1, 11) AS k WHERE has(rv, sh[k]))
SELECT if(sp = rv[1], '1 first view', '2 later view') AS position, if(ifNull(o.buys, 0) >= vx.maxb, '1 most bought', '2 not most bought') AS popularity,
       round(sum(w)) AS w_imps, sum(c) AS clicks, sum(p) AS buys, round(100 * clicks / w_imps, 2) AS ctr_w, round(100 * buys / w_imps, 2) AS conv_w
FROM imp LEFT JOIN pop o ON o.pid = imp.sp JOIN vx ON vx.rid = imp.rid GROUP BY position, popularity ORDER BY position, popularity;
