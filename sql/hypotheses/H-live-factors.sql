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

-- 7a session relation by page and strategy, live (reference = other category in the same page and strategy)
WITH
prod AS (SELECT pid, any(cat) AS cat, any(sub) AS sub FROM (SELECT product_id::String AS pid, category::String AS cat, subcategory::String AS sub FROM shop.catalog UNION ALL SELECT product_id::String, category::String, subcategory::String FROM shop.catalog_updates WHERE change::String = 'new_product') GROUP BY pid),
fb AS (SELECT f.request_id::String AS rid, f.shown::Array(String) AS sh, f.clicked::String AS ck, f.purchased::String AS pu, if(s.mv LIKE 'rules%', 'rules', 'best sellers') AS strategy
       FROM {TEAM}.feedback f LEFT JOIN (SELECT request_id::String AS rid, any(model_version::String) AS mv FROM {TEAM}.submissions GROUP BY rid) s ON s.rid = f.request_id::String
       WHERE length(f.shown::Array(String)) = 10 AND s.mv NOT LIKE 'explore%'),
rq AS (SELECT request_id::String AS rid, context.page::String AS page, arrayMap(v -> v.product_id::String, recent_views::Array(JSON)) AS rv FROM shop.requests WHERE request_id::String IN (SELECT rid FROM fb) AND context.page::String IN ('product', 'category')),
rvc AS (SELECT rid, groupArrayIf(p.sub, i < n) AS esub, groupArrayIf(p.cat, i < n) AS ecat, anyIf(p.sub, i = n) AS lsub, anyIf(p.cat, i = n) AS lcat
        FROM (SELECT rid, length(rv) AS n, arrayJoin(arrayEnumerate(rv)) AS i, rv[i] AS pid FROM rq WHERE length(rv) > 0) x JOIN prod p ON p.pid = x.pid GROUP BY rid),
imp AS (SELECT fb.rid AS rid, rq.page AS page, fb.strategy AS strategy, rq.rv AS rv, k, fb.sh[k] AS sp, 1 / log2(k + 1) AS w, fb.ck = fb.sh[k] AS c, fb.pu = fb.sh[k] AS p
        FROM fb JOIN rq ON rq.rid = fb.rid ARRAY JOIN range(1, 11) AS k),
cells AS (
  SELECT imp.page AS page, imp.strategy AS strategy, multiIf(length(imp.rv) = 0, '8 no recent views', imp.sp = imp.rv[-1], '0 last view', has(arrayPopBack(imp.rv), imp.sp), '1 other recent view',
                 pr.sub = r.lsub, '2 same subcat as last', has(r.esub, pr.sub), '3 same subcat as earlier only', pr.cat = r.lcat, '4 same cat as last',
                 has(r.ecat, pr.cat), '5 same cat as earlier only', '6 other category') AS cell,
         count() AS imps, round(sum(w)) AS w_imps, sum(c) AS clicks, sum(p) AS buys
  FROM imp JOIN prod pr ON pr.pid = imp.sp LEFT JOIN rvc r ON r.rid = imp.rid GROUP BY page, strategy, cell)
SELECT page, strategy, cell, imps, w_imps, clicks, buys, round(100 * clicks / w_imps, 3) AS ctr_w, round(100 * buys / w_imps, 3) AS conv_w,
       round((clicks / w_imps) / (maxIf(clicks, cell = '6 other category') OVER (PARTITION BY page, strategy) / maxIf(w_imps, cell = '6 other category') OVER (PARTITION BY page, strategy)), 2) AS click_x,
       round((buys / w_imps) / (maxIf(buys, cell = '6 other category') OVER (PARTITION BY page, strategy) / maxIf(w_imps, cell = '6 other category') OVER (PARTITION BY page, strategy)), 2) AS buy_x,
       round(click_x * exp(-sqrt(1 / greatest(clicks, 1) + 1 / maxIf(clicks, cell = '6 other category') OVER (PARTITION BY page, strategy))), 2) AS click_lo,
       round(click_x * exp(sqrt(1 / greatest(clicks, 1) + 1 / maxIf(clicks, cell = '6 other category') OVER (PARTITION BY page, strategy))), 2) AS click_hi
FROM cells ORDER BY page, strategy, cell;

-- 7b history: category shown by the old carousel against the categories of the recent views, by page (per request)
WITH
prod AS (SELECT product_id::String AS pid, any(category::String) AS cat FROM shop.catalog GROUP BY pid),
s AS (SELECT request_id::String AS rid, context.page::String AS page, shown::Array(String) AS sh,
             arrayMap(v -> v.product_id::String, recent_views::Array(JSON)) AS rv, ifNull(clicked::Nullable(String), '') AS ck, ifNull(purchased::Nullable(String), '') AS pu
      FROM shop.history_sessions WHERE context.page::String IN ('product', 'category')),
vc AS (SELECT rid, anyIf(p.cat, i = n) AS lcat, groupArrayIf(p.cat, i < n) AS ecat
       FROM (SELECT rid, length(rv) AS n, arrayJoin(arrayEnumerate(rv)) AS i, rv[i] AS pid FROM s) v JOIN prod p ON p.pid = v.pid GROUP BY rid),
sc AS (SELECT rid, anyIf(p.cat, k = 1) AS scat, uniqExact(p.cat) AS ncat
       FROM (SELECT rid, arrayJoin(arrayEnumerate(sh)) AS k, sh[k] AS pid FROM s) v JOIN prod p ON p.pid = v.pid GROUP BY rid)
SELECT s.page AS page, multiIf(sc.scat = vc.lcat, '1 shown category = last view category', has(vc.ecat, sc.scat), '2 = an earlier view category only', '3 = no recent view category') AS shown_cat,
       count() AS requests, round(100 * requests / sum(requests) OVER (PARTITION BY page), 1) AS pct, round(avg(sc.ncat), 2) AS cats_per_list,
       countIf(s.ck != '') AS clicks, countIf(s.pu != '') AS buys, round(100 * clicks / requests, 2) AS ctr, round(100 * buys / requests, 3) AS conv
FROM s JOIN vc ON vc.rid = s.rid JOIN sc ON sc.rid = s.rid
GROUP BY page, shown_cat ORDER BY page, shown_cat;

-- 7c live per request: page x strategy x shopper type
SELECT r.context.page::String AS page, if(s.mv LIKE 'rules%', 'rules', 'best sellers') AS strategy, if(r.is_new_user::Bool, 'new', 'returning') AS shopper,
       count() AS requests, countIf(f.clicked::String != '') AS clicks, countIf(f.purchased::String != '') AS buys, round(100 * clicks / requests, 2) AS ctr, round(100 * buys / requests, 2) AS conv
FROM {TEAM}.feedback f JOIN shop.requests r ON r.request_id::String = f.request_id::String
LEFT JOIN (SELECT request_id::String AS rid, any(model_version::String) AS mv FROM {TEAM}.submissions GROUP BY rid) s ON s.rid = f.request_id::String
WHERE s.mv NOT LIKE 'explore%' GROUP BY page, strategy, shopper ORDER BY page, strategy, shopper;

-- 8a age of the last recent view, live: re-shown last view and same-subcategory products, by page and strategy
WITH
prod AS (SELECT pid, any(sub) AS sub FROM (SELECT product_id::String AS pid, subcategory::String AS sub FROM shop.catalog UNION ALL SELECT product_id::String, subcategory::String FROM shop.catalog_updates WHERE change::String = 'new_product') GROUP BY pid),
fb AS (SELECT f.request_id::String AS rid, f.shown::Array(String) AS sh, f.clicked::String AS ck, f.purchased::String AS pu, if(s.mv LIKE 'rules%', 'rules', 'best sellers') AS strategy
       FROM {TEAM}.feedback f LEFT JOIN (SELECT request_id::String AS rid, any(model_version::String) AS mv FROM {TEAM}.submissions GROUP BY rid) s ON s.rid = f.request_id::String
       WHERE length(f.shown::Array(String)) = 10 AND s.mv NOT LIKE 'explore%'),
rq AS (SELECT request_id::String AS rid, context.page::String AS page, (recent_views::Array(JSON))[-1].product_id::String AS lv,
              dateDiff('millisecond', (recent_views::Array(JSON))[-1].ts::DateTime64(3), ts::DateTime64(3)) / 1000 AS age
       FROM shop.requests WHERE request_id::String IN (SELECT rid FROM fb) AND length(recent_views::Array(JSON)) > 0),
imp AS (SELECT rq.page AS page, fb.strategy AS strategy, rq.lv AS lv, rq.age AS age, fb.sh[k] AS sp, 1 / log2(k + 1) AS w, fb.ck = fb.sh[k] AS c, fb.pu = fb.sh[k] AS p
        FROM fb JOIN rq ON rq.rid = fb.rid ARRAY JOIN range(1, 11) AS k)
SELECT page, strategy, if(imp.sp = imp.lv, '1 last view', '2 same subcat as last view') AS shown,
       multiIf(age < 30, '1 <30s', age < 120, '2 30s-2min', age < 600, '3 2-10min', '4 >10min') AS age_bucket,
       count() AS imps, round(sum(w)) AS w_imps, sum(c) AS clicks, sum(p) AS buys, round(100 * clicks / w_imps, 2) AS ctr_w, round(100 * buys / w_imps, 2) AS conv_w
FROM imp JOIN prod a ON a.pid = imp.sp JOIN prod b ON b.pid = imp.lv
WHERE imp.sp = imp.lv OR a.sub = b.sub
GROUP BY page, strategy, shown, age_bucket ORDER BY page, strategy, shown, age_bucket;

-- 8b age of the last recent view, live: share of requests by page
SELECT context.page::String AS page, count() AS requests,
       round(100 * countIf(a < 30) / requests, 1) AS pct_lt30s, round(100 * countIf(a >= 30 AND a < 120) / requests, 1) AS pct_30s_2m,
       round(100 * countIf(a >= 120 AND a < 600) / requests, 1) AS pct_2_10m, round(100 * countIf(a >= 600) / requests, 1) AS pct_gt10m, round(quantile(0.5)(a)) AS median_s
FROM (SELECT context, dateDiff('millisecond', (recent_views::Array(JSON))[-1].ts::DateTime64(3), ts::DateTime64(3)) / 1000 AS a FROM shop.requests WHERE length(recent_views::Array(JSON)) > 0)
GROUP BY page ORDER BY page;

-- 8c age of the last recent view, history carousel: re-shown last view and same-subcategory products, by page
WITH
prod AS (SELECT product_id::String AS pid, any(subcategory::String) AS sub FROM shop.catalog GROUP BY pid),
s AS (SELECT context.page::String AS page, shown::Array(String) AS sh, (recent_views::Array(JSON))[-1].product_id::String AS lv,
             dateDiff('millisecond', (recent_views::Array(JSON))[-1].ts::DateTime64(3), ts::DateTime64(3)) / 1000 AS age,
             ifNull(clicked::Nullable(String), '') AS ck, ifNull(purchased::Nullable(String), '') AS pu
      FROM shop.history_sessions WHERE context.page::String IN ('product', 'category')),
imp AS (SELECT page, lv, age, sh[k] AS sp, 1 / log2(k + 1) AS w, ck = sh[k] AS c, pu = sh[k] AS p FROM s ARRAY JOIN range(1, 11) AS k)
SELECT page, if(imp.sp = imp.lv, '1 last view', '2 same subcat as last view') AS shown,
       multiIf(age < 30, '1 <30s', age < 120, '2 30s-2min', age < 600, '3 2-10min', '4 >10min') AS age_bucket,
       count() AS imps, round(sum(w)) AS w_imps, sum(c) AS clicks, sum(p) AS buys, round(100 * clicks / w_imps, 2) AS ctr_w, round(100 * buys / w_imps, 2) AS conv_w
FROM imp JOIN prod a ON a.pid = imp.sp JOIN prod b ON b.pid = imp.lv
WHERE imp.sp = imp.lv OR a.sub = b.sub
GROUP BY page, shown, age_bucket ORDER BY page, shown, age_bucket;

-- 8d history: next view after a request without a click, relative to the last recent view, by page (10% sample, within 10 min). NOTE: recent_views are not in history_events, so this is the next session, not the same one
WITH
prod AS (SELECT product_id::String AS pid, any(category::String) AS cat, any(subcategory::String) AS sub FROM shop.catalog GROUP BY pid),
s AS (SELECT user_id::String AS u, ts::DateTime64(3) AS rt, context.page::String AS page,
             if(length(recent_views::Array(JSON)) = 0, '', (recent_views::Array(JSON))[-1].product_id::String) AS lv
      FROM shop.history_sessions WHERE cityHash64(request_id::String) % 10 = 0 AND clicked::Nullable(String) IS NULL),
ev AS (SELECT user_id::String AS u, ts::DateTime64(3) AS et, product_id::String AS np FROM shop.history_events
       WHERE event_type::String = 'view' AND user_id::String IN (SELECT u FROM s)),
j AS (SELECT s.page AS page, s.lv AS lv, ev.np AS np, ev.et AS et, s.rt AS rt FROM s ASOF LEFT JOIN ev ON ev.u = s.u AND ev.et > s.rt)
SELECT page, multiIf(np = '' OR dateDiff('second', rt, et) > 600, '5 no view within 10 min', lv = '', '6 no recent views', np = lv, '1 same product', b.sub = a.sub, '2 same subcategory', b.cat = a.cat, '3 same category', '4 other category') AS next_view,
       count() AS requests, round(100 * requests / sum(requests) OVER (PARTITION BY page), 1) AS pct
FROM j LEFT JOIN prod a ON a.pid = j.lv LEFT JOIN prod b ON b.pid = j.np
GROUP BY page, next_view ORDER BY page, next_view;

-- 8e live: next view after a request without a click (shop.events, within 10 min). Same caveat: recent_views are not in shop.events
WITH
prod AS (SELECT pid, any(cat) AS cat, any(sub) AS sub FROM (SELECT product_id::String AS pid, category::String AS cat, subcategory::String AS sub FROM shop.catalog UNION ALL SELECT product_id::String, category::String, subcategory::String FROM shop.catalog_updates WHERE change::String = 'new_product') GROUP BY pid),
s AS (SELECT r.user_id::String AS u, r.ts::DateTime64(3) AS rt, r.context.page::String AS page,
             if(length(r.recent_views::Array(JSON)) = 0, '', (r.recent_views::Array(JSON))[-1].product_id::String) AS lv
      FROM shop.requests r JOIN {TEAM}.feedback f ON f.request_id::String = r.request_id::String
      WHERE f.clicked::String = '' AND r.ts::DateTime64(3) < (SELECT max(ts::DateTime64(3)) FROM shop.events) - INTERVAL 10 MINUTE),
ev AS (SELECT user_id::String AS u, ts::DateTime64(3) AS et, product_id::String AS np FROM shop.events WHERE event_type::String = 'view' AND user_id::String IN (SELECT u FROM s)),
j AS (SELECT s.page AS page, s.lv AS lv, ev.np AS np, ev.et AS et, s.rt AS rt FROM s ASOF LEFT JOIN ev ON ev.u = s.u AND ev.et > s.rt)
SELECT page, multiIf(np = '' OR dateDiff('second', rt, et) > 600, '5 no view within 10 min', lv = '', '6 no recent views', np = lv, '1 same product', b.sub = a.sub, '2 same subcategory', b.cat = a.cat, '3 same category', '4 other category') AS next_view,
       count() AS requests, round(100 * requests / sum(requests) OVER (PARTITION BY page), 1) AS pct
FROM j LEFT JOIN prod a ON a.pid = j.lv LEFT JOIN prod b ON b.pid = j.np
GROUP BY page, next_view ORDER BY page, next_view;

-- 8f check: are recent views present in the event logs? (exact user, product, ts; history 1% sample and live last hour)
SELECT 'history' AS src, count() AS n, countIf(e.u != '') AS matched
FROM (SELECT user_id::String AS u, (recent_views::Array(JSON))[-1].product_id::String AS p, (recent_views::Array(JSON))[-1].ts::DateTime64(3) AS t
      FROM shop.history_sessions WHERE cityHash64(request_id::String) % 100 = 0 AND length(recent_views::Array(JSON)) > 0) s
LEFT JOIN (SELECT user_id::String AS u, product_id::String AS p, ts::DateTime64(3) AS t FROM shop.history_events WHERE event_type::String = 'view'
           AND user_id::String IN (SELECT user_id::String FROM shop.history_sessions WHERE cityHash64(request_id::String) % 100 = 0)) e ON e.u = s.u AND e.p = s.p AND e.t = s.t
UNION ALL
SELECT 'live', count(), countIf(e.u != '')
FROM (SELECT user_id::String AS u, (recent_views::Array(JSON))[-1].product_id::String AS p, (recent_views::Array(JSON))[-1].ts::DateTime64(3) AS t
      FROM shop.requests WHERE length(recent_views::Array(JSON)) > 0 AND ts::DateTime64(3) > now() - INTERVAL 1 HOUR) s
LEFT JOIN (SELECT user_id::String AS u, product_id::String AS p, ts::DateTime64(3) AS t FROM shop.events WHERE event_type::String = 'view') e ON e.u = s.u AND e.p = s.p AND e.t = s.t;
