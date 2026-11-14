-- H-live-factors: the multipliers of rules.py measured on live feedback (all strategies), per impression, slot-weighted (w = 1/log2(slot+1)).
-- Rates: ctr_w, conv_w = clicks or buys / sum of slot weights. *_x = ratio to the reference cell; *_lo/_hi = rough 68% range, exp(+-sqrt(1/n + 1/n_ref)).
-- Run: uv run scripts/q.py sql/hypotheses/H-live-factors.sql [title filter]

-- 0 data window
SELECT min(f.ts::DateTime64(3)) AS first, max(f.ts::DateTime64(3)) AS last, count() AS requests, countIf(s.mv LIKE 'rules%') AS rules_requests,
       minIf(f.ts::DateTime64(3), s.mv LIKE 'rules%') AS rules_first, countIf(f.clicked::String != '') AS clicks, countIf(f.purchased::String != '') AS buys,
       round(count() / dateDiff('second', min(f.ts::DateTime64(3)), max(f.ts::DateTime64(3))) * 3600) AS requests_per_hour
FROM {TEAM}.feedback f LEFT JOIN (SELECT request_id::String AS rid, any(model_version::String) AS mv FROM {TEAM}.submissions GROUP BY rid) s ON s.rid = f.request_id::String
WHERE length(f.shown::Array(String)) = 10;

-- 1 session relation of the shown product (all shoppers), reference = other category
WITH
prod AS (SELECT pid, any(cat) AS cat, any(sub) AS sub FROM (SELECT product_id::String AS pid, category::String AS cat, subcategory::String AS sub FROM shop.catalog UNION ALL SELECT product_id::String, category::String, subcategory::String FROM shop.catalog_updates WHERE change::String = 'new_product') GROUP BY pid),
fb AS (SELECT request_id::String AS rid, shown::Array(String) AS sh, clicked::String AS ck, purchased::String AS pu FROM {TEAM}.feedback WHERE length(shown::Array(String)) = 10),
rq AS (SELECT request_id::String AS rid, arrayMap(v -> v.product_id::String, recent_views::Array(JSON)) AS rv FROM shop.requests WHERE request_id::String IN (SELECT rid FROM fb)),
rvc AS (SELECT rid, groupArrayIf(p.sub, i < n) AS esub, groupArrayIf(p.cat, i < n) AS ecat, anyIf(p.sub, i = n) AS lsub, anyIf(p.cat, i = n) AS lcat
        FROM (SELECT rid, length(rv) AS n, arrayJoin(arrayEnumerate(rv)) AS i, rv[i] AS pid FROM rq WHERE length(rv) > 0) x JOIN prod p ON p.pid = x.pid GROUP BY rid),
imp AS (SELECT fb.rid AS rid, rq.rv AS rv, k, fb.sh[k] AS sp, 1 / log2(k + 1) AS w, fb.ck = fb.sh[k] AS c, fb.pu = fb.sh[k] AS p
        FROM fb JOIN rq ON rq.rid = fb.rid ARRAY JOIN range(1, 11) AS k),
cells AS (
  SELECT multiIf(length(imp.rv) = 0, '8 no recent views', imp.sp = imp.rv[-1], '0 last view', has(arrayPopBack(imp.rv), imp.sp), '1 other recent view',
                 pr.sub = r.lsub, '2 same subcat as last', has(r.esub, pr.sub), '3 same subcat as earlier only', pr.cat = r.lcat, '4 same cat as last',
                 has(r.ecat, pr.cat), '5 same cat as earlier only', '6 other category') AS cell,
         count() AS imps, round(sum(w)) AS w_imps, sum(c) AS clicks, sum(p) AS buys
  FROM imp JOIN prod pr ON pr.pid = imp.sp LEFT JOIN rvc r ON r.rid = imp.rid GROUP BY cell)
SELECT cell, imps, w_imps, clicks, buys, round(100 * clicks / w_imps, 3) AS ctr_w, round(100 * buys / w_imps, 3) AS conv_w,
       round((clicks / w_imps) / (maxIf(clicks, cell = '6 other category') OVER () / maxIf(w_imps, cell = '6 other category') OVER ()), 2) AS click_x,
       round((buys / w_imps) / (maxIf(buys, cell = '6 other category') OVER () / maxIf(w_imps, cell = '6 other category') OVER ()), 2) AS buy_x,
       round(click_x * exp(-sqrt(1 / greatest(clicks, 1) + 1 / maxIf(clicks, cell = '6 other category') OVER ())), 2) AS click_lo,
       round(click_x * exp(sqrt(1 / greatest(clicks, 1) + 1 / maxIf(clicks, cell = '6 other category') OVER ())), 2) AS click_hi,
       round(buy_x * exp(-sqrt(1 / greatest(buys, 1) + 1 / maxIf(buys, cell = '6 other category') OVER ())), 2) AS buy_lo,
       round(buy_x * exp(sqrt(1 / greatest(buys, 1) + 1 / maxIf(buys, cell = '6 other category') OVER ())), 2) AS buy_hi
FROM cells ORDER BY cell;

-- 2 history relation, returning shoppers, reference = never seen
WITH
fb AS (SELECT request_id::String AS rid, ts::DateTime64(3) AS t, shown::Array(String) AS sh, clicked::String AS ck, purchased::String AS pu FROM {TEAM}.feedback WHERE length(shown::Array(String)) = 10),
rq AS (SELECT request_id::String AS rid, user_id::String AS u, ts::DateTime64(3) AS rt FROM shop.requests WHERE request_id::String IN (SELECT rid FROM fb) AND NOT is_new_user::Bool),
imp AS (SELECT rq.u AS u, rq.rt AS rt, fb.sh[k] AS sp, 1 / log2(k + 1) AS w, fb.ck = fb.sh[k] AS c, fb.pu = fb.sh[k] AS p FROM fb JOIN rq ON rq.rid = fb.rid ARRAY JOIN range(1, 11) AS k),
hist AS (SELECT user_id::String AS u, product_id::String AS sp, countIf(event_type::String = 'purchase') AS hb, countIf(event_type::String = 'view') AS hv
         FROM shop.history_events WHERE user_id::String IN (SELECT u FROM rq) GROUP BY u, sp),
today AS (SELECT u, sp, min(bt) AS bt FROM (
            SELECT user_id::String AS u, product_id::String AS sp, ts::DateTime64(3) AS bt FROM shop.events WHERE event_type::String = 'purchase' AND user_id::String IN (SELECT u FROM rq)
            UNION ALL
            SELECT r.u, f.pu, f.t FROM fb f JOIN rq r ON r.rid = f.rid WHERE f.pu != '') GROUP BY u, sp),
cells AS (
  SELECT multiIf(h.hb > 0, '0 bought in history', d.bt > toDateTime64('2000-01-01', 3) AND d.bt < imp.rt, '1 bought today, before request',
                 h.hv >= 10, '2 viewed 10+, not bought', h.hv >= 3, '3 viewed 3-9, not bought', h.hv = 2, '4 viewed 2, not bought', h.hv = 1, '5 viewed 1, not bought', '6 never seen') AS cell,
         count() AS imps, round(sum(w)) AS w_imps, sum(c) AS clicks, sum(p) AS buys
  FROM imp LEFT JOIN hist h ON h.u = imp.u AND h.sp = imp.sp LEFT JOIN today d ON d.u = imp.u AND d.sp = imp.sp GROUP BY cell)
SELECT cell, imps, w_imps, clicks, buys, round(100 * clicks / w_imps, 3) AS ctr_w, round(100 * buys / w_imps, 3) AS conv_w,
       round((clicks / w_imps) / (maxIf(clicks, cell = '6 never seen') OVER () / maxIf(w_imps, cell = '6 never seen') OVER ()), 2) AS click_x,
       round((buys / w_imps) / (maxIf(buys, cell = '6 never seen') OVER () / maxIf(w_imps, cell = '6 never seen') OVER ()), 2) AS buy_x,
       round(buy_x * exp(-sqrt(1 / greatest(buys, 1) + 1 / maxIf(buys, cell = '6 never seen') OVER ())), 2) AS buy_lo,
       round(buy_x * exp(sqrt(1 / greatest(buys, 1) + 1 / maxIf(buys, cell = '6 never seen') OVER ())), 2) AS buy_hi
FROM cells ORDER BY cell;

-- 3 favourite category share of history views, returning shoppers, split by session, reference = share up to 0.1 in the same split
WITH
prod AS (SELECT pid, any(cat) AS cat FROM (SELECT product_id::String AS pid, category::String AS cat FROM shop.catalog UNION ALL SELECT product_id::String, category::String FROM shop.catalog_updates WHERE change::String = 'new_product') GROUP BY pid),
fb AS (SELECT request_id::String AS rid, shown::Array(String) AS sh, clicked::String AS ck, purchased::String AS pu FROM {TEAM}.feedback WHERE length(shown::Array(String)) = 10),
rq AS (SELECT request_id::String AS rid, user_id::String AS u, arrayMap(v -> v.product_id::String, recent_views::Array(JSON)) AS rv FROM shop.requests WHERE request_id::String IN (SELECT rid FROM fb) AND NOT is_new_user::Bool),
rvc AS (SELECT rid, groupUniqArray(p.cat) AS vcats FROM (SELECT rid, arrayJoin(rv) AS pid FROM rq) x JOIN prod p ON p.pid = x.pid GROUP BY rid),
imp AS (SELECT rq.rid AS rid, rq.u AS u, length(rq.rv) > 0 AS has_views, fb.sh[k] AS sp, 1 / log2(k + 1) AS w, fb.ck = fb.sh[k] AS c, fb.pu = fb.sh[k] AS p FROM fb JOIN rq ON rq.rid = fb.rid ARRAY JOIN range(1, 11) AS k),
share AS (SELECT u, cat, n / sum(n) OVER (PARTITION BY u) AS s FROM (
            SELECT e.user_id::String AS u, p.cat AS cat, count() AS n FROM shop.history_events e JOIN prod p ON p.pid = e.product_id::String
            WHERE e.event_type::String = 'view' AND e.user_id::String IN (SELECT u FROM rq) GROUP BY u, cat)),
cells AS (
  SELECT multiIf(NOT imp.has_views, '1 no views', has(r.vcats, pr.cat), '2 views, shown in a viewed category', '3 views, other category') AS session,
         multiIf(sh.s = 0, '0', sh.s <= 0.1, '0-0.1', sh.s <= 0.3, '0.1-0.3', sh.s <= 0.6, '0.3-0.6', '0.6+') AS share_bucket,
         count() AS imps, round(sum(w)) AS w_imps, sum(c) AS clicks, sum(p) AS buys
  FROM imp JOIN prod pr ON pr.pid = imp.sp LEFT JOIN share sh ON sh.u = imp.u AND sh.cat = pr.cat LEFT JOIN rvc r ON r.rid = imp.rid GROUP BY session, share_bucket)
SELECT session, share_bucket, imps, w_imps, clicks, buys, round(100 * clicks / w_imps, 3) AS ctr_w, round(100 * buys / w_imps, 3) AS conv_w,
       round((clicks / w_imps) / (sumIf(clicks, share_bucket IN ('0', '0-0.1')) OVER (PARTITION BY session) / sumIf(w_imps, share_bucket IN ('0', '0-0.1')) OVER (PARTITION BY session)), 2) AS click_x,
       round((buys / w_imps) / (sumIf(buys, share_bucket IN ('0', '0-0.1')) OVER (PARTITION BY session) / sumIf(w_imps, share_bucket IN ('0', '0-0.1')) OVER (PARTITION BY session)), 2) AS buy_x,
       round(click_x * exp(-sqrt(1 / greatest(clicks, 1) + 1 / sumIf(clicks, share_bucket IN ('0', '0-0.1')) OVER (PARTITION BY session))), 2) AS click_lo,
       round(click_x * exp(sqrt(1 / greatest(clicks, 1) + 1 / sumIf(clicks, share_bucket IN ('0', '0-0.1')) OVER (PARTITION BY session))), 2) AS click_hi
FROM cells ORDER BY session, share_bucket;

-- 4 segment android-south x category x shopper type, reference = rest, same category and shopper type
WITH
prod AS (SELECT pid, any(cat) AS cat FROM (SELECT product_id::String AS pid, category::String AS cat FROM shop.catalog UNION ALL SELECT product_id::String, category::String FROM shop.catalog_updates WHERE change::String = 'new_product') GROUP BY pid),
fb AS (SELECT request_id::String AS rid, shown::Array(String) AS sh, clicked::String AS ck, purchased::String AS pu FROM {TEAM}.feedback WHERE length(shown::Array(String)) = 10),
rq AS (SELECT request_id::String AS rid, is_new_user::Bool AS nu,
              context.device::String = 'android' AND context.region::String IN ('Andalucía', 'Canarias', 'Murcia') AS south
       FROM shop.requests WHERE request_id::String IN (SELECT rid FROM fb)),
imp AS (SELECT rq.nu AS nu, rq.south AS south, fb.sh[k] AS sp, 1 / log2(k + 1) AS w, fb.ck = fb.sh[k] AS c, fb.pu = fb.sh[k] AS p FROM fb JOIN rq ON rq.rid = fb.rid ARRAY JOIN range(1, 11) AS k),
cells AS (SELECT if(nu, 'new', 'returning') AS shopper, pr.cat AS category, if(south, 'android-south', 'rest') AS segment,
                 count() AS imps, round(sum(w)) AS w_imps, sum(c) AS clicks, sum(p) AS buys
          FROM imp JOIN prod pr ON pr.pid = imp.sp GROUP BY shopper, category, segment)
SELECT shopper, category, segment, imps, w_imps, clicks, buys, round(100 * clicks / w_imps, 3) AS ctr_w, round(100 * buys / w_imps, 3) AS conv_w,
       round((clicks / w_imps) / (maxIf(clicks, segment = 'rest') OVER (PARTITION BY shopper, category) / maxIf(w_imps, segment = 'rest') OVER (PARTITION BY shopper, category)), 2) AS click_x,
       round((buys / w_imps) / (maxIf(buys, segment = 'rest') OVER (PARTITION BY shopper, category) / maxIf(w_imps, segment = 'rest') OVER (PARTITION BY shopper, category)), 2) AS buy_x,
       round(click_x * exp(-sqrt(1 / greatest(clicks, 1) + 1 / greatest(maxIf(clicks, segment = 'rest') OVER (PARTITION BY shopper, category), 1))), 2) AS click_lo,
       round(click_x * exp(sqrt(1 / greatest(clicks, 1) + 1 / greatest(maxIf(clicks, segment = 'rest') OVER (PARTITION BY shopper, category), 1))), 2) AS click_hi
FROM cells ORDER BY shopper, category, segment;

-- 4b segment, all categories pooled (requests x 10 slots)
WITH
fb AS (SELECT request_id::String AS rid, shown::Array(String) AS sh, clicked::String AS ck, purchased::String AS pu FROM {TEAM}.feedback WHERE length(shown::Array(String)) = 10),
rq AS (SELECT request_id::String AS rid, is_new_user::Bool AS nu,
              context.device::String = 'android' AND context.region::String IN ('Andalucía', 'Canarias', 'Murcia') AS south
       FROM shop.requests WHERE request_id::String IN (SELECT rid FROM fb))
SELECT if(nu, 'new', 'returning') AS shopper, if(south, 'android-south', 'rest') AS segment, count() * 10 AS imps, round(count() * 4.543) AS w_imps,
       countIf(ck != '') AS clicks, countIf(pu != '') AS buys, round(100 * clicks / w_imps, 3) AS ctr_w, round(100 * buys / w_imps, 3) AS conv_w
FROM fb JOIN rq ON rq.rid = fb.rid GROUP BY shopper, segment ORDER BY shopper, segment;

-- 5 two-way session x history relation, returning shoppers, cells with 300+ weighted impressions
WITH
prod AS (SELECT pid, any(cat) AS cat, any(sub) AS sub FROM (SELECT product_id::String AS pid, category::String AS cat, subcategory::String AS sub FROM shop.catalog UNION ALL SELECT product_id::String, category::String, subcategory::String FROM shop.catalog_updates WHERE change::String = 'new_product') GROUP BY pid),
fb AS (SELECT request_id::String AS rid, ts::DateTime64(3) AS t, shown::Array(String) AS sh, clicked::String AS ck, purchased::String AS pu FROM {TEAM}.feedback WHERE length(shown::Array(String)) = 10),
rq AS (SELECT request_id::String AS rid, user_id::String AS u, ts::DateTime64(3) AS rt, arrayMap(v -> v.product_id::String, recent_views::Array(JSON)) AS rv
       FROM shop.requests WHERE request_id::String IN (SELECT rid FROM fb) AND NOT is_new_user::Bool),
rvc AS (SELECT rid, groupArrayIf(p.sub, i < n) AS esub, groupArrayIf(p.cat, i < n) AS ecat, anyIf(p.sub, i = n) AS lsub, anyIf(p.cat, i = n) AS lcat
        FROM (SELECT rid, length(rv) AS n, arrayJoin(arrayEnumerate(rv)) AS i, rv[i] AS pid FROM rq WHERE length(rv) > 0) x JOIN prod p ON p.pid = x.pid GROUP BY rid),
imp AS (SELECT fb.rid AS rid, rq.u AS u, rq.rt AS rt, rq.rv AS rv, fb.sh[k] AS sp, 1 / log2(k + 1) AS w, fb.ck = fb.sh[k] AS c, fb.pu = fb.sh[k] AS p
        FROM fb JOIN rq ON rq.rid = fb.rid ARRAY JOIN range(1, 11) AS k),
hist AS (SELECT user_id::String AS u, product_id::String AS sp, countIf(event_type::String = 'purchase') AS hb, countIf(event_type::String = 'view') AS hv
         FROM shop.history_events WHERE user_id::String IN (SELECT u FROM rq) GROUP BY u, sp),
today AS (SELECT u, sp, min(bt) AS bt FROM (
            SELECT user_id::String AS u, product_id::String AS sp, ts::DateTime64(3) AS bt FROM shop.events WHERE event_type::String = 'purchase' AND user_id::String IN (SELECT u FROM rq)
            UNION ALL SELECT r.u, f.pu, f.t FROM fb f JOIN rq r ON r.rid = f.rid WHERE f.pu != '') GROUP BY u, sp),
cells AS (
  SELECT multiIf(length(imp.rv) = 0, '8 no recent views', imp.sp = imp.rv[-1], '0 last view', has(arrayPopBack(imp.rv), imp.sp), '1 other recent view',
                 pr.sub = r.lsub, '2 same subcat as last', has(r.esub, pr.sub), '3 same subcat as earlier only', pr.cat = r.lcat, '4 same cat as last',
                 has(r.ecat, pr.cat), '5 same cat as earlier only', '6 other category') AS session,
         multiIf(h.hb > 0, '0 bought in history', d.bt > toDateTime64('2000-01-01', 3) AND d.bt < imp.rt, '1 bought today',
                 h.hv >= 3, '3 viewed 3+, not bought', h.hv >= 1, '4 viewed 1-2, not bought', '6 never seen') AS history,
         count() AS imps, round(sum(w)) AS w_imps, sum(c) AS clicks, sum(p) AS buys
  FROM imp JOIN prod pr ON pr.pid = imp.sp LEFT JOIN rvc r ON r.rid = imp.rid
       LEFT JOIN hist h ON h.u = imp.u AND h.sp = imp.sp LEFT JOIN today d ON d.u = imp.u AND d.sp = imp.sp GROUP BY session, history),
rated AS (
  SELECT session, history, imps, w_imps, clicks, buys, round(100 * clicks / w_imps, 3) AS ctr_w, round(100 * buys / w_imps, 3) AS conv_w,
         round((clicks / w_imps) / (maxIf(clicks, session = '6 other category' AND history = '6 never seen') OVER () / maxIf(w_imps, session = '6 other category' AND history = '6 never seen') OVER ()), 2) AS click_x,
         round((buys / w_imps) / (maxIf(buys, session = '6 other category' AND history = '6 never seen') OVER () / maxIf(w_imps, session = '6 other category' AND history = '6 never seen') OVER ()), 2) AS buy_x
  FROM cells)
SELECT * FROM rated WHERE w_imps >= 300 ORDER BY session, history;

-- 6 slot curve, rules against best sellers
WITH
fb AS (SELECT f.request_id::String AS rid, f.shown::Array(String) AS sh, f.clicked::String AS ck, f.purchased::String AS pu,
              if(s.mv LIKE 'rules%', 'rules', if(s.mv LIKE 'explore%', 'explore', 'best sellers')) AS strategy
       FROM {TEAM}.feedback f LEFT JOIN (SELECT request_id::String AS rid, any(model_version::String) AS mv FROM {TEAM}.submissions GROUP BY rid) s ON s.rid = f.request_id::String
       WHERE length(f.shown::Array(String)) = 10),
slots AS (SELECT strategy, k AS slot, count() AS imps, 1 / log2(k + 1) AS w, countIf(ck = sh[k]) AS clicks, countIf(pu = sh[k]) AS buys
          FROM fb ARRAY JOIN range(1, 11) AS k WHERE strategy != 'explore' GROUP BY strategy, slot)
SELECT strategy, slot, imps, clicks, buys, round(100 * clicks / imps, 3) AS ctr, round(100 * buys / imps, 3) AS conv, round(w, 3) AS attention,
       round((clicks / imps) / (sum(clicks) OVER (PARTITION BY strategy) / sum(imps * w) OVER (PARTITION BY strategy)), 3) AS ctr_over_mean_w,
       round(ctr_over_mean_w / w, 2) AS ratio_to_attention
FROM slots ORDER BY strategy, slot;
