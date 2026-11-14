-- H-session-shape: does the whole list of recent views carry more than the last one? (repeats, concentration, second-to-last view, price direction, number of views)
-- Live, every strategy pooled, impressions slot-weighted, w = 1/log2(slot+1); ctr_w, conv_w per 100 weighted impressions. A cut matters if it moves a cell by more than 30%.
-- Run: uv run scripts/q.py sql/hypotheses/H-session-shape.sql [title filter]

-- 1 number of recent views and concentration (distinct subcategories) against the relation to the last view
WITH
prod AS (SELECT pid, any(cat) AS cat, any(sub) AS sub FROM (SELECT product_id::String AS pid, category::String AS cat, subcategory::String AS sub FROM shop.catalog UNION ALL SELECT product_id::String, category::String, subcategory::String FROM shop.catalog_updates WHERE change::String = 'new_product') GROUP BY pid),
fb AS (SELECT request_id::String AS rid, shown::Array(String) AS sh, clicked::String AS ck, purchased::String AS pu FROM {TEAM}.feedback WHERE length(shown::Array(String)) = 10),
rq AS (SELECT request_id::String AS rid, arrayMap(v -> v.product_id::String, recent_views::Array(JSON)) AS rv FROM shop.requests WHERE request_id::String IN (SELECT rid FROM fb) AND length(recent_views::Array(JSON)) > 0),
vx AS (SELECT rid, arrayMap(x -> x.2, arraySort(groupArray((i, p.sub)))) AS vs, arrayMap(x -> x.2, arraySort(groupArray((i, p.cat)))) AS vc FROM (SELECT rid, arrayJoin(arrayEnumerate(rv)) AS i, rv[i] AS pid FROM rq) x JOIN prod p ON p.pid = x.pid GROUP BY rid),
imp AS (SELECT rq.rv AS rv, vx.vs AS vs, vx.vc AS vc, fb.sh[k] AS sp, 1 / log2(k + 1) AS w, fb.ck = fb.sh[k] AS c, fb.pu = fb.sh[k] AS p
        FROM fb JOIN rq ON rq.rid = fb.rid JOIN vx ON vx.rid = fb.rid ARRAY JOIN range(1, 11) AS k WHERE length(vx.vs) = length(rq.rv))
SELECT multiIf(length(rv) = 1, '1 one view', length(arrayDistinct(vs)) = 1, '2 2+ views, one subcat', length(arrayDistinct(vc)) = 1, '3 2+ views, one cat', '4 2+ views, several cats') AS shape,
       multiIf(sp = rv[-1], '1 last view', has(rv, sp), '2 earlier view', pr.sub = vs[-1], '3 same subcat as last', pr.cat = vc[-1], '4 same cat as last', '5 other') AS relation,
       count() AS imps, round(sum(w)) AS w_imps, sum(c) AS clicks, sum(p) AS buys, round(100 * clicks / w_imps, 3) AS ctr_w, round(100 * buys / w_imps, 3) AS conv_w
FROM imp JOIN prod pr ON pr.pid = imp.sp GROUP BY shape, relation ORDER BY shape, relation;

-- 2 re-shown recent view viewed twice or more against once; and share of requests with a repeated view
WITH
fb AS (SELECT request_id::String AS rid, shown::Array(String) AS sh, clicked::String AS ck, purchased::String AS pu FROM {TEAM}.feedback WHERE length(shown::Array(String)) = 10),
rq AS (SELECT request_id::String AS rid, arrayMap(v -> v.product_id::String, recent_views::Array(JSON)) AS rv FROM shop.requests WHERE request_id::String IN (SELECT rid FROM fb) AND length(recent_views::Array(JSON)) > 0)
SELECT if(sp = rv[-1], 'last view', 'earlier view') AS which, if(countEqual(rv, sp) > 1, '2+ times', 'once') AS times, count() AS imps, round(sum(1 / log2(k + 1))) AS w_imps,
       countIf(fb.ck = sp) AS clicks, countIf(fb.pu = sp) AS buys, round(100 * clicks / w_imps, 3) AS ctr_w, round(100 * buys / w_imps, 3) AS conv_w,
       round(100 * (SELECT countIf(length(rv) > length(arrayDistinct(rv))) / count() FROM rq), 1) AS pct_requests_with_repeat
FROM fb JOIN rq ON rq.rid = fb.rid ARRAY JOIN range(1, 11) AS k, fb.sh AS sp WHERE has(rq.rv, fb.sh[k]) AND sp = fb.sh[k]
GROUP BY which, times ORDER BY which, times;

-- 3 second-to-last view: same subcategory as the last view, as the second-to-last only, as an older view only (requests with 2+ views)
WITH
prod AS (SELECT pid, any(cat) AS cat, any(sub) AS sub FROM (SELECT product_id::String AS pid, category::String AS cat, subcategory::String AS sub FROM shop.catalog UNION ALL SELECT product_id::String, category::String, subcategory::String FROM shop.catalog_updates WHERE change::String = 'new_product') GROUP BY pid),
fb AS (SELECT request_id::String AS rid, shown::Array(String) AS sh, clicked::String AS ck, purchased::String AS pu FROM {TEAM}.feedback WHERE length(shown::Array(String)) = 10),
rq AS (SELECT request_id::String AS rid, arrayMap(v -> v.product_id::String, recent_views::Array(JSON)) AS rv FROM shop.requests WHERE request_id::String IN (SELECT rid FROM fb) AND length(recent_views::Array(JSON)) > 1),
vx AS (SELECT rid, arrayMap(x -> x.2, arraySort(groupArray((i, p.sub)))) AS vs, arrayMap(x -> x.2, arraySort(groupArray((i, p.cat)))) AS vc FROM (SELECT rid, arrayJoin(arrayEnumerate(rv)) AS i, rv[i] AS pid FROM rq) x JOIN prod p ON p.pid = x.pid GROUP BY rid),
imp AS (SELECT rq.rv AS rv, vx.vs AS vs, vx.vc AS vc, fb.sh[k] AS sp, 1 / log2(k + 1) AS w, fb.ck = fb.sh[k] AS c, fb.pu = fb.sh[k] AS p
        FROM fb JOIN rq ON rq.rid = fb.rid JOIN vx ON vx.rid = fb.rid ARRAY JOIN range(1, 11) AS k WHERE length(vx.vs) = length(rq.rv))
SELECT multiIf(has(rv, sp), '0 a recent view', pr.sub = vs[-1], '1 subcat of last', pr.sub = vs[-2], '2 subcat of 2nd last only', has(vs, pr.sub), '3 subcat of an older view only',
               pr.cat = vc[-1], '4 cat of last', pr.cat = vc[-2], '5 cat of 2nd last only', has(vc, pr.cat), '6 cat of an older view only', '7 other') AS relation,
       count() AS imps, round(sum(w)) AS w_imps, sum(c) AS clicks, sum(p) AS buys, round(100 * clicks / w_imps, 3) AS ctr_w, round(100 * buys / w_imps, 3) AS conv_w
FROM imp JOIN prod pr ON pr.pid = imp.sp GROUP BY relation ORDER BY relation;

-- 4 price direction of the views (last against first) x price of the shown product against the last view's, same category as the last view, not a recent view
WITH
prod AS (SELECT pid, any(cat) AS cat, any(price) AS price FROM (SELECT product_id::String AS pid, category::String AS cat, price_eur::Float64 AS price FROM shop.catalog UNION ALL SELECT product_id::String, category::String, price_eur::Float64 FROM shop.catalog_updates WHERE change::String = 'new_product') GROUP BY pid),
fb AS (SELECT request_id::String AS rid, shown::Array(String) AS sh, clicked::String AS ck, purchased::String AS pu FROM {TEAM}.feedback WHERE length(shown::Array(String)) = 10),
rq AS (SELECT request_id::String AS rid, arrayMap(v -> v.product_id::String, recent_views::Array(JSON)) AS rv FROM shop.requests WHERE request_id::String IN (SELECT rid FROM fb) AND length(recent_views::Array(JSON)) > 0),
vx AS (SELECT rid, arrayMap(x -> x.2, arraySort(groupArray((i, p.price)))) AS vp, arrayMap(x -> x.2, arraySort(groupArray((i, p.cat)))) AS vc FROM (SELECT rid, arrayJoin(arrayEnumerate(rv)) AS i, rv[i] AS pid FROM rq) x JOIN prod p ON p.pid = x.pid GROUP BY rid),
imp AS (SELECT rq.rv AS rv, vx.vp AS vp, vx.vc AS vc, fb.sh[k] AS sp, 1 / log2(k + 1) AS w, fb.ck = fb.sh[k] AS c, fb.pu = fb.sh[k] AS p
        FROM fb JOIN rq ON rq.rid = fb.rid JOIN vx ON vx.rid = fb.rid ARRAY JOIN range(1, 11) AS k WHERE length(vx.vp) = length(rq.rv))
SELECT multiIf(length(vp) = 1, '0 one view', vp[-1] > 1.2 * vp[1], '1 trading up', vp[-1] < vp[1] / 1.2, '2 trading down', '3 flat') AS direction,
       multiIf(pr.price > 1.2 * vp[-1], '1 dearer than last', pr.price < vp[-1] / 1.2, '2 cheaper than last', '3 similar') AS shown_price,
       count() AS imps, round(sum(w)) AS w_imps, sum(c) AS clicks, sum(p) AS buys, round(100 * clicks / w_imps, 3) AS ctr_w, round(100 * buys / w_imps, 3) AS conv_w
FROM imp JOIN prod pr ON pr.pid = imp.sp WHERE pr.cat = vc[-1] AND NOT has(rv, sp)
GROUP BY direction, shown_price ORDER BY direction, shown_price;

-- 5 history support: number of views and concentration against the relation to the last view (carousel shows the last view's category)
WITH
prod AS (SELECT product_id::String AS pid, any(category::String) AS cat, any(subcategory::String) AS sub FROM shop.catalog GROUP BY pid),
s AS (SELECT request_id::String AS rid, shown::Array(String) AS sh, arrayMap(v -> v.product_id::String, recent_views::Array(JSON)) AS rv,
             ifNull(clicked::Nullable(String), '') AS ck, ifNull(purchased::Nullable(String), '') AS pu
      FROM shop.history_sessions WHERE context.page::String IN ('product', 'category') AND length(recent_views::Array(JSON)) > 0 AND cityHash64(request_id::String) % 4 = 0),
vx AS (SELECT rid, arrayMap(x -> x.2, arraySort(groupArray((i, p.sub)))) AS vs FROM (SELECT rid, arrayJoin(arrayEnumerate(rv)) AS i, rv[i] AS pid FROM s) x JOIN prod p ON p.pid = x.pid GROUP BY rid),
imp AS (SELECT s.rv AS rv, vx.vs AS vs, sh[k] AS sp, 1 / log2(k + 1) AS w, ck = sh[k] AS c, pu = sh[k] AS p FROM s JOIN vx ON vx.rid = s.rid ARRAY JOIN range(1, 11) AS k WHERE length(vx.vs) = length(s.rv))
SELECT multiIf(length(rv) = 1, '1 one view', length(arrayDistinct(vs)) = 1, '2 2+ views, one subcat', '3 2+ views, several subcats') AS shape,
       multiIf(sp = rv[-1], '1 last view', has(rv, sp), '2 earlier view', pr.sub = vs[-1], '3 same subcat as last', has(vs, pr.sub), '4 subcat of an earlier view', '5 same cat, other subcat') AS relation,
       count() AS imps, round(sum(w)) AS w_imps, sum(c) AS clicks, sum(p) AS buys, round(100 * clicks / w_imps, 3) AS ctr_w, round(100 * buys / w_imps, 3) AS conv_w
FROM imp JOIN prod pr ON pr.pid = imp.sp GROUP BY shape, relation ORDER BY shape, relation;

-- 6 live: subcategory and category of the first view against the last view's, products that are not recent views (requests with 2+ views)
WITH
prod AS (SELECT pid, any(cat) AS cat, any(sub) AS sub FROM (SELECT product_id::String AS pid, category::String AS cat, subcategory::String AS sub FROM shop.catalog UNION ALL SELECT product_id::String, category::String, subcategory::String FROM shop.catalog_updates WHERE change::String = 'new_product') GROUP BY pid),
fb AS (SELECT request_id::String AS rid, shown::Array(String) AS sh, clicked::String AS ck, purchased::String AS pu FROM {TEAM}.feedback WHERE length(shown::Array(String)) = 10),
rq AS (SELECT request_id::String AS rid, arrayMap(v -> v.product_id::String, recent_views::Array(JSON)) AS rv FROM shop.requests WHERE request_id::String IN (SELECT rid FROM fb) AND length(recent_views::Array(JSON)) > 1),
vx AS (SELECT rid, arrayMap(x -> x.2, arraySort(groupArray((i, p.sub)))) AS vs, arrayMap(x -> x.2, arraySort(groupArray((i, p.cat)))) AS vc FROM (SELECT rid, arrayJoin(arrayEnumerate(rv)) AS i, rv[i] AS pid FROM rq) x JOIN prod p ON p.pid = x.pid GROUP BY rid),
imp AS (SELECT rq.rv AS rv, vx.vs AS vs, vx.vc AS vc, fb.sh[k] AS sp, 1 / log2(k + 1) AS w, fb.ck = fb.sh[k] AS c, fb.pu = fb.sh[k] AS p
        FROM fb JOIN rq ON rq.rid = fb.rid JOIN vx ON vx.rid = fb.rid ARRAY JOIN range(1, 11) AS k WHERE length(vx.vs) = length(rq.rv) AND NOT has(rq.rv, fb.sh[k]))
SELECT multiIf(pr.sub = vs[1] AND pr.sub = vs[-1], '1 sub of first and last', pr.sub = vs[1], '2 sub of first only', pr.sub = vs[-1], '3 sub of last only', has(vs, pr.sub), '4 sub of a middle view',
               pr.cat = vc[1] AND pr.cat = vc[-1], '5 cat of first and last', pr.cat = vc[1], '6 cat of first only', pr.cat = vc[-1], '7 cat of last only', has(vc, pr.cat), '8 cat of a middle view', '9 other') AS relation,
       round(sum(w)) AS w_imps, sum(c) AS clicks, sum(p) AS buys, round(100 * clicks / w_imps, 3) AS ctr_w, round(100 * buys / w_imps, 3) AS conv_w
FROM imp JOIN prod pr ON pr.pid = imp.sp GROUP BY relation ORDER BY relation;

-- 7 live, non-home pages: history cart against history view of the shown product, by session relation; best-seller lists (not chosen per shopper) and all lists
WITH
prod AS (SELECT pid, any(cat) AS cat FROM (SELECT product_id::String AS pid, category::String AS cat FROM shop.catalog UNION ALL SELECT product_id::String, category::String FROM shop.catalog_updates WHERE change::String = 'new_product') GROUP BY pid),
fb AS (SELECT f.request_id::String AS rid, f.shown::Array(String) AS sh, f.clicked::String AS ck, f.purchased::String AS pu, s.mv LIKE 'baseline%' OR s.mv LIKE 'quartz%' AS best
       FROM {TEAM}.feedback f JOIN (SELECT request_id::String AS rid, any(model_version::String) AS mv FROM {TEAM}.submissions GROUP BY rid) s ON s.rid = f.request_id::String
       WHERE length(f.shown::Array(String)) = 10),
rq AS (SELECT request_id::String AS rid, user_id::String AS u, arrayMap(v -> v.product_id::String, recent_views::Array(JSON)) AS rv FROM shop.requests
       WHERE request_id::String IN (SELECT rid FROM fb) AND context.page::String != 'home' AND length(recent_views::Array(JSON)) > 0),
hu AS (SELECT user_id::String AS u, product_id::String AS hp, countIf(event_type::String = 'view') AS v, countIf(event_type::String = 'add_to_cart') AS a, countIf(event_type::String = 'purchase') AS b
       FROM shop.history_events WHERE user_id::String IN (SELECT u FROM rq) GROUP BY u, hp),
vc AS (SELECT rid, groupArray(p.cat) AS cats FROM (SELECT rid, arrayJoin(rv) AS pid FROM rq) x JOIN prod p ON p.pid = x.pid GROUP BY rid),
imp AS (SELECT rq.rid AS rid, rq.u AS u, rq.rv AS rv, fb.best AS best, fb.sh[k] AS sp, 1 / log2(k + 1) AS w, fb.ck = fb.sh[k] AS c, fb.pu = fb.sh[k] AS bp FROM fb JOIN rq ON rq.rid = fb.rid ARRAY JOIN range(1, 11) AS k)
SELECT lists, session, history, count() AS imps, round(sum(w)) AS w_imps, sum(c) AS clicks, sum(bp) AS buys, round(100 * clicks / w_imps, 3) AS ctr_w, round(100 * buys / w_imps, 3) AS conv_w
FROM (SELECT 'all lists' AS lists, imp.*, multiIf(has(imp.rv, imp.sp), '1 recent view', has(vc.cats, pr.cat), '2 session category', '3 other category') AS session,
             multiIf(h.b > 0, '4 bought', h.a > 0, '1 carted not bought', h.v > 0, '2 viewed not carted', '3 never seen') AS history
      FROM imp JOIN prod pr ON pr.pid = imp.sp LEFT JOIN vc ON vc.rid = imp.rid LEFT JOIN hu h ON h.u = imp.u AND h.hp = imp.sp
      UNION ALL
      SELECT 'best sellers', imp.*, multiIf(has(imp.rv, imp.sp), '1 recent view', has(vc.cats, pr.cat), '2 session category', '3 other category'),
             multiIf(h.b > 0, '4 bought', h.a > 0, '1 carted not bought', h.v > 0, '2 viewed not carted', '3 never seen')
      FROM imp JOIN prod pr ON pr.pid = imp.sp LEFT JOIN vc ON vc.rid = imp.rid LEFT JOIN hu h ON h.u = imp.u AND h.hp = imp.sp WHERE imp.best)
GROUP BY lists, session, history ORDER BY lists, session, history;
