-- H-slot-order: is each list sorted? Click rate by slot over the attention curve 1/log2(slot+1), for rules2 and jasper; which relation types sit too high or too low.
-- rules2 = rules2|slate|m202e1|romesco (also -h, -n routes), jasper = ranker. ctr_w = clicks per 100 weighted impressions, w = 1/log2(slot+1).
-- Run: uv run scripts/q.py sql/hypotheses/H-slot-order.sql [title filter]

-- 1 slot curve: click rate per slot over the list mean, divided by the attention weight (1 = attention only; a sorted list falls below 1 at the bottom)
WITH
fb AS (SELECT f.request_id::String AS rid, f.shown::Array(String) AS sh, f.clicked::String AS ck, f.purchased::String AS pu,
              multiIf(s.mv LIKE 'rules2%' OR s.mv LIKE 'slate%' OR s.mv LIKE 'm202e1%' OR s.mv LIKE 'romesco%', 'rules2', s.mv LIKE 'jasper%', 'jasper', 'other') AS strategy
       FROM {TEAM}.feedback f JOIN (SELECT request_id::String AS rid, any(model_version::String) AS mv FROM {TEAM}.submissions GROUP BY rid) s ON s.rid = f.request_id::String
       WHERE length(f.shown::Array(String)) = 10),
slots AS (SELECT strategy, k AS slot, count() AS imps, 1 / log2(k + 1) AS w, countIf(ck = sh[k]) AS clicks, countIf(pu = sh[k]) AS buys
          FROM fb ARRAY JOIN range(1, 11) AS k WHERE strategy != 'other' GROUP BY strategy, slot)
SELECT strategy, slot, imps, clicks, buys, round(100 * clicks / imps, 3) AS ctr, round(w, 3) AS attention,
       round((clicks / imps) / (sum(clicks) OVER (PARTITION BY strategy) / sum(imps * w) OVER (PARTITION BY strategy)) / w, 2) AS ratio_to_attention
FROM slots ORDER BY strategy, slot;

-- 2 relation type by slot band: where each type is placed (share in slots 1-3) and how it converts per weighted impression in each band
WITH
prod AS (SELECT pid, any(cat) AS cat, any(sub) AS sub FROM (SELECT product_id::String AS pid, category::String AS cat, subcategory::String AS sub FROM shop.catalog UNION ALL SELECT product_id::String, category::String, subcategory::String FROM shop.catalog_updates WHERE change::String = 'new_product') GROUP BY pid),
fb AS (SELECT f.request_id::String AS rid, f.shown::Array(String) AS sh, f.clicked::String AS ck, f.purchased::String AS pu,
              multiIf(s.mv LIKE 'rules2%' OR s.mv LIKE 'slate%' OR s.mv LIKE 'm202e1%' OR s.mv LIKE 'romesco%', 'rules2', s.mv LIKE 'jasper%', 'jasper', 'other') AS strategy
       FROM {TEAM}.feedback f JOIN (SELECT request_id::String AS rid, any(model_version::String) AS mv FROM {TEAM}.submissions GROUP BY rid) s ON s.rid = f.request_id::String
       WHERE length(f.shown::Array(String)) = 10 AND strategy != 'other'),
rq AS (SELECT request_id::String AS rid, arrayMap(v -> v.product_id::String, recent_views::Array(JSON)) AS rv FROM shop.requests WHERE request_id::String IN (SELECT rid FROM fb) AND length(recent_views::Array(JSON)) > 0),
vx AS (SELECT rid, arrayMap(x -> x.2, arraySort(groupArray((i, p.sub)))) AS vs, arrayMap(x -> x.2, arraySort(groupArray((i, p.cat)))) AS vc FROM (SELECT rid, arrayJoin(arrayEnumerate(rv)) AS i, rv[i] AS pid FROM rq) x JOIN prod p ON p.pid = x.pid GROUP BY rid),
imp AS (SELECT fb.strategy AS strategy, rq.rv AS rv, vx.vs AS vs, vx.vc AS vc, arraySort((c, i) -> (-countEqual(vx.vc, c), i), vx.vc, arrayEnumerate(vx.vc))[1] AS mcat,
               k, fb.sh[k] AS sp, 1 / log2(k + 1) AS w, fb.ck = fb.sh[k] AS c, fb.pu = fb.sh[k] AS p
        FROM fb JOIN rq ON rq.rid = fb.rid JOIN vx ON vx.rid = fb.rid ARRAY JOIN range(1, 11) AS k WHERE length(vx.vs) = length(rq.rv)),
cells AS (SELECT strategy, multiIf(length(arrayDistinct(rv)) = 1 AND sp = rv[1], '1 only view', sp = rv[1], '2 first of 2+ views', has(rv, sp), '3 later view', pr.sub = vs[-1], '4 subcat of last',
                                   pr.cat = mcat, '5 majority cat', has(vc, pr.cat), '6 other viewed cat', '7 other') AS cell, k <= 3 AS top3, w, c, p
          FROM imp JOIN prod pr ON pr.pid = imp.sp)
SELECT strategy, cell, count() AS imps, round(100 * countIf(top3) / imps, 1) AS pct_in_top3, round(sumIf(w, top3)) AS w_top3, sumIf(c, top3) AS clicks_top3, round(100 * clicks_top3 / w_top3, 2) AS ctr_w_top3,
       round(sumIf(w, NOT top3)) AS w_rest, sumIf(c, NOT top3) AS clicks_rest, round(100 * clicks_rest / w_rest, 2) AS ctr_w_rest, sum(p) AS buys, round(100 * buys / sum(w), 3) AS conv_w
FROM cells GROUP BY strategy, cell ORDER BY strategy, cell;
