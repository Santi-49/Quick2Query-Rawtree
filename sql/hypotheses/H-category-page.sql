-- H-category-page: on category pages, is the browsed category the majority of the recent views rather than the last view's?
-- Live impressions are slot-weighted, w = 1/log2(slot+1); ctr_w, conv_w = clicks or buys per 100 weighted impressions.
-- Strategy labels: rules2 = rules2|slate|m202e1|romesco, jasper = ranker, best sellers = baseline. Run: uv run scripts/q.py sql/hypotheses/H-category-page.sql [title filter]

-- 1 live per request, requests with recent views: conversion by page and strategy (the premise)
SELECT r.context.page::String AS page,
       multiIf(s.mv LIKE 'rules2%' OR s.mv LIKE 'slate%' OR s.mv LIKE 'm202e1%' OR s.mv LIKE 'romesco%', 'rules2', s.mv LIKE 'jasper%', 'jasper', s.mv LIKE 'baseline%', 'best sellers', s.mv LIKE 'rules@%', 'rules', 'other') AS strategy,
       count() AS requests, countIf(f.clicked::String != '') AS clicks, countIf(f.purchased::String != '') AS buys, round(100 * clicks / requests, 2) AS ctr, round(100 * buys / requests, 2) AS conv
FROM {TEAM}.feedback f JOIN shop.requests r ON r.request_id::String = f.request_id::String
JOIN (SELECT request_id::String AS rid, any(model_version::String) AS mv FROM {TEAM}.submissions GROUP BY rid) s ON s.rid = f.request_id::String
WHERE length(r.recent_views::Array(JSON)) > 0 AND page IN ('product', 'category') GROUP BY page, strategy ORDER BY strategy, page;

-- 2 history per request: the carousel's single shown category against the last view's, the majority's, any view's
WITH
prod AS (SELECT product_id::String AS pid, any(category::String) AS cat FROM shop.catalog GROUP BY pid),
s AS (SELECT request_id::String AS rid, context.page::String AS page, (shown::Array(String))[1] AS s1, arrayMap(v -> v.product_id::String, recent_views::Array(JSON)) AS rv,
             clicked::Nullable(String) IS NOT NULL AS c, purchased::Nullable(String) IS NOT NULL AS p
      FROM shop.history_sessions WHERE context.page::String IN ('product', 'category') AND length(recent_views::Array(JSON)) > 0),
vx AS (SELECT rid, arrayMap(x -> x.2, arraySort(groupArray((i, p.cat)))) AS vc FROM (SELECT rid, arrayJoin(arrayEnumerate(rv)) AS i, rv[i] AS pid FROM s) x JOIN prod p ON p.pid = x.pid GROUP BY rid)
SELECT s.page AS page, if(length(arrayDistinct(vx.vc)) = 1, 'one category', 'mixed') AS views,
       multiIf(pr.cat = vx.vc[-1] AND pr.cat = arraySort((c, i) -> (-countEqual(vx.vc, c), -i), vx.vc, arrayEnumerate(vx.vc))[1], '1 = last = majority', pr.cat = vx.vc[-1], '2 = last, not majority',
               pr.cat = arraySort((c, i) -> (-countEqual(vx.vc, c), -i), vx.vc, arrayEnumerate(vx.vc))[1], '3 = majority, not last', has(vx.vc, pr.cat), '4 = another view', '5 = none') AS shown_cat,
       count() AS requests, sum(c) AS clicks, sum(p) AS buys, round(100 * clicks / requests, 2) AS ctr, round(100 * buys / requests, 3) AS conv
FROM s JOIN vx ON vx.rid = s.rid JOIN prod pr ON pr.pid = s.s1
GROUP BY page, views, shown_cat ORDER BY page, views, shown_cat;

-- 3 live impressions on requests whose majority category differs from the last view's: relation of the shown product, by page
WITH
prod AS (SELECT pid, any(cat) AS cat, any(sub) AS sub FROM (SELECT product_id::String AS pid, category::String AS cat, subcategory::String AS sub FROM shop.catalog UNION ALL SELECT product_id::String, category::String, subcategory::String FROM shop.catalog_updates WHERE change::String = 'new_product') GROUP BY pid),
fb AS (SELECT request_id::String AS rid, shown::Array(String) AS sh, clicked::String AS ck, purchased::String AS pu FROM {TEAM}.feedback WHERE length(shown::Array(String)) = 10),
rq AS (SELECT request_id::String AS rid, context.page::String AS page, arrayMap(v -> v.product_id::String, recent_views::Array(JSON)) AS rv
       FROM shop.requests WHERE request_id::String IN (SELECT rid FROM fb) AND length(recent_views::Array(JSON)) > 1 AND context.page::String IN ('product', 'category')),
vx AS (SELECT rid, arrayMap(x -> x.2, arraySort(groupArray((i, p.cat)))) AS vc FROM (SELECT rid, arrayJoin(arrayEnumerate(rv)) AS i, rv[i] AS pid FROM rq) x JOIN prod p ON p.pid = x.pid GROUP BY rid),
imp AS (SELECT rq.page AS page, rq.rv AS rv, vx.vc AS vc, arraySort((c, i) -> (-countEqual(vx.vc, c), -i), vx.vc, arrayEnumerate(vx.vc))[1] AS mcat, fb.sh[k] AS sp, 1 / log2(k + 1) AS w, fb.ck = fb.sh[k] AS c, fb.pu = fb.sh[k] AS p
        FROM fb JOIN rq ON rq.rid = fb.rid JOIN vx ON vx.rid = fb.rid ARRAY JOIN range(1, 11) AS k WHERE length(vx.vc) = length(rq.rv))
SELECT page, multiIf(has(rv, sp), '0 a recent view', pr.cat = vc[-1], '1 last view category', pr.cat = mcat, '2 majority category', has(vc, pr.cat), '3 another view category', '4 other category') AS relation,
       count() AS imps, round(sum(w)) AS w_imps, sum(c) AS clicks, sum(p) AS buys, round(100 * clicks / w_imps, 3) AS ctr_w, round(100 * buys / w_imps, 3) AS conv_w
FROM imp JOIN prod pr ON pr.pid = imp.sp WHERE mcat != vc[-1]
GROUP BY page, relation ORDER BY page, relation;

-- 4 live impressions, requests with 2+ views: same subcategory as the last view against the majority subcategory, by page
WITH
prod AS (SELECT pid, any(cat) AS cat, any(sub) AS sub FROM (SELECT product_id::String AS pid, category::String AS cat, subcategory::String AS sub FROM shop.catalog UNION ALL SELECT product_id::String, category::String, subcategory::String FROM shop.catalog_updates WHERE change::String = 'new_product') GROUP BY pid),
fb AS (SELECT request_id::String AS rid, shown::Array(String) AS sh, clicked::String AS ck, purchased::String AS pu FROM {TEAM}.feedback WHERE length(shown::Array(String)) = 10),
rq AS (SELECT request_id::String AS rid, context.page::String AS page, arrayMap(v -> v.product_id::String, recent_views::Array(JSON)) AS rv
       FROM shop.requests WHERE request_id::String IN (SELECT rid FROM fb) AND length(recent_views::Array(JSON)) > 1 AND context.page::String IN ('product', 'category')),
vx AS (SELECT rid, arrayMap(x -> x.2, arraySort(groupArray((i, p.sub)))) AS vs FROM (SELECT rid, arrayJoin(arrayEnumerate(rv)) AS i, rv[i] AS pid FROM rq) x JOIN prod p ON p.pid = x.pid GROUP BY rid),
imp AS (SELECT rq.page AS page, rq.rv AS rv, vx.vs AS vs, arraySort((c, i) -> (-countEqual(vx.vs, c), -i), vx.vs, arrayEnumerate(vx.vs))[1] AS msub, fb.sh[k] AS sp, 1 / log2(k + 1) AS w, fb.ck = fb.sh[k] AS c, fb.pu = fb.sh[k] AS p
        FROM fb JOIN rq ON rq.rid = fb.rid JOIN vx ON vx.rid = fb.rid ARRAY JOIN range(1, 11) AS k WHERE length(vx.vs) = length(rq.rv))
SELECT page, msub = vs[-1] AS majority_is_last, multiIf(has(rv, sp), '0 a recent view', pr.sub = vs[-1], '1 last view subcategory', pr.sub = msub, '2 majority subcategory', has(vs, pr.sub), '3 another view subcategory', '4 other') AS relation,
       count() AS imps, round(sum(w)) AS w_imps, sum(c) AS clicks, sum(p) AS buys, round(100 * clicks / w_imps, 3) AS ctr_w, round(100 * buys / w_imps, 3) AS conv_w
FROM imp JOIN prod pr ON pr.pid = imp.sp
GROUP BY page, majority_is_last, relation ORDER BY page, majority_is_last, relation;

-- 5 live: next organic view after a request without a click, within 10 min, by page (recent views are not in shop.events, so this is usually another session)
WITH
prod AS (SELECT pid, any(cat) AS cat, any(sub) AS sub FROM (SELECT product_id::String AS pid, category::String AS cat, subcategory::String AS sub FROM shop.catalog UNION ALL SELECT product_id::String, category::String, subcategory::String FROM shop.catalog_updates WHERE change::String = 'new_product') GROUP BY pid),
s AS (SELECT r.user_id::String AS u, r.ts::DateTime64(3) AS rt, r.context.page::String AS page, (r.recent_views::Array(JSON))[-1].product_id::String AS lv
      FROM shop.requests r JOIN {TEAM}.feedback f ON f.request_id::String = r.request_id::String
      WHERE f.clicked::String = '' AND length(r.recent_views::Array(JSON)) > 0 AND r.context.page::String IN ('product', 'category')
        AND r.ts::DateTime64(3) < (SELECT max(ts::DateTime64(3)) FROM shop.events) - INTERVAL 10 MINUTE),
ev AS (SELECT user_id::String AS u, ts::DateTime64(3) AS et, product_id::String AS np FROM shop.events WHERE event_type::String = 'view' AND user_id::String IN (SELECT u FROM s)),
j AS (SELECT s.page AS page, s.lv AS lv, ev.np AS np, ev.et AS et, s.rt AS rt FROM s ASOF LEFT JOIN ev ON ev.u = s.u AND ev.et > s.rt)
SELECT page, multiIf(np = '' OR dateDiff('second', rt, et) > 600, '5 none within 10 min', np = lv, '1 same product', b.sub = a.sub, '2 same subcategory', b.cat = a.cat, '3 same category', '4 other category') AS next_view,
       count() AS requests, round(100 * requests / sum(requests) OVER (PARTITION BY page), 1) AS pct
FROM j LEFT JOIN prod a ON a.pid = j.lv LEFT JOIN prod b ON b.pid = j.np
GROUP BY page, next_view ORDER BY page, next_view;
