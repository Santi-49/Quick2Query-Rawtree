-- H-home-personal: on home requests of returning shoppers, does the shopper's own history predict the purchase of a shown product?
-- History: home requests from 15 Oct 07:00 (last 30 days) against organic history before that date, unless the title says "before each request" (ASOF join).
-- Impressions are weighted by 1/log2(slot+1); wconv = purchases / weighted impressions (a slot-1-equivalent rate).

-- category rank by history views (30/30)
WITH imp AS (SELECT user_id::String AS u, sh[k] AS sp, k, 1 / log2(k + 1) AS w, ck, pu
             FROM (SELECT user_id, shown::Array(String) AS sh, ifNull(clicked::String, '') AS ck, ifNull(purchased::String, '') AS pu, arrayJoin(range(1, 11)) AS k
                   FROM shop.history_sessions WHERE context.page::String = 'home' AND ts::DateTime64(3) >= '2026-10-15 07:00:00')),
     uc AS (SELECT e.user_id::String AS u, c.category::String AS cat, countIf(e.event_type::String = 'view') AS nv, countIf(e.event_type::String = 'purchase') AS nb
            FROM shop.history_events e JOIN shop.catalog c ON c.product_id::String = e.product_id::String
            WHERE e.ts::DateTime64(3) < '2026-10-15 07:00:00' GROUP BY u, cat),
     rk AS (SELECT u, cat, nv, nb, row_number() OVER (PARTITION BY u ORDER BY nv DESC, cat) AS rv, if(nb > 0, row_number() OVER (PARTITION BY u ORDER BY nb DESC, nv DESC, cat), 0) AS rb, sum(nv) OVER (PARTITION BY u) AS tot FROM uc),
     us AS (SELECT DISTINCT u FROM uc)
SELECT multiIf(imp.u NOT IN (SELECT u FROM us), '9 no history', rk.nv = 0, '5 never viewed cat', rk.rv = 1, '1 top', rk.rv = 2, '2 second', rk.rv = 3, '3 third', '4 4th+') AS view_rank,
       count() AS n, round(sum(w)) AS wsum, countIf(ck = sp) AS clicks, countIf(pu = sp) AS buys,
       round(100 * clicks / wsum, 3) AS wctr, round(100 * buys / wsum, 4) AS wconv
FROM imp JOIN shop.catalog c ON c.product_id::String = imp.sp
LEFT JOIN rk ON rk.u = imp.u AND rk.cat = c.category::String
GROUP BY view_rank ORDER BY view_rank;

-- category rank by history purchases (30/30)
WITH imp AS (SELECT user_id::String AS u, sh[k] AS sp, k, 1 / log2(k + 1) AS w, ck, pu
             FROM (SELECT user_id, shown::Array(String) AS sh, ifNull(clicked::String, '') AS ck, ifNull(purchased::String, '') AS pu, arrayJoin(range(1, 11)) AS k
                   FROM shop.history_sessions WHERE context.page::String = 'home' AND ts::DateTime64(3) >= '2026-10-15 07:00:00')),
     uc AS (SELECT e.user_id::String AS u, c.category::String AS cat, countIf(e.event_type::String = 'view') AS nv, countIf(e.event_type::String = 'purchase') AS nb
            FROM shop.history_events e JOIN shop.catalog c ON c.product_id::String = e.product_id::String
            WHERE e.ts::DateTime64(3) < '2026-10-15 07:00:00' GROUP BY u, cat),
     rk AS (SELECT u, cat, nv, nb, row_number() OVER (PARTITION BY u ORDER BY nb DESC, nv DESC, cat) AS rb FROM uc),
     us AS (SELECT DISTINCT u FROM uc)
SELECT multiIf(imp.u NOT IN (SELECT u FROM us), '9 no history', rk.nb = 0, '5 never bought cat', rk.rb = 1, '1 top', rk.rb = 2, '2 second', rk.rb = 3, '3 third', '4 4th+') AS buy_rank,
       count() AS n, round(sum(w)) AS wsum, countIf(ck = sp) AS clicks, countIf(pu = sp) AS buys,
       round(100 * clicks / wsum, 3) AS wctr, round(100 * buys / wsum, 4) AS wconv
FROM imp JOIN shop.catalog c ON c.product_id::String = imp.sp
LEFT JOIN rk ON rk.u = imp.u AND rk.cat = c.category::String
GROUP BY buy_rank ORDER BY buy_rank;

-- category share of history views (30/30)
WITH imp AS (SELECT user_id::String AS u, sh[k] AS sp, k, 1 / log2(k + 1) AS w, ck, pu
             FROM (SELECT user_id, shown::Array(String) AS sh, ifNull(clicked::String, '') AS ck, ifNull(purchased::String, '') AS pu, arrayJoin(range(1, 11)) AS k
                   FROM shop.history_sessions WHERE context.page::String = 'home' AND ts::DateTime64(3) >= '2026-10-15 07:00:00')),
     uc AS (SELECT e.user_id::String AS u, c.category::String AS cat, count() AS nv
            FROM shop.history_events e JOIN shop.catalog c ON c.product_id::String = e.product_id::String
            WHERE e.ts::DateTime64(3) < '2026-10-15 07:00:00' AND e.event_type::String = 'view' GROUP BY u, cat),
     sh AS (SELECT u, cat, nv / sum(nv) OVER (PARTITION BY u) AS s FROM uc)
SELECT multiIf(sh.s = 0, '0 none', sh.s < 0.05, '1 <5%', sh.s < 0.15, '2 5-15%', sh.s < 0.3, '3 15-30%', sh.s < 0.5, '4 30-50%', '5 50%+') AS share,
       count() AS n, round(sum(w)) AS wsum, countIf(ck = sp) AS clicks, countIf(pu = sp) AS buys, round(avg(sh.s), 3) AS mean_share,
       round(100 * clicks / wsum, 3) AS wctr, round(100 * buys / wsum, 4) AS wconv
FROM imp JOIN shop.catalog c ON c.product_id::String = imp.sp
LEFT JOIN sh ON sh.u = imp.u AND sh.cat = c.category::String
WHERE imp.u IN (SELECT u FROM uc)
GROUP BY share ORDER BY share;

-- product viewed before by view count, and bought before (30/30)
WITH imp AS (SELECT user_id::String AS u, sh[k] AS sp, k, 1 / log2(k + 1) AS w, ck, pu
             FROM (SELECT user_id, shown::Array(String) AS sh, ifNull(clicked::String, '') AS ck, ifNull(purchased::String, '') AS pu, arrayJoin(range(1, 11)) AS k
                   FROM shop.history_sessions WHERE context.page::String = 'home' AND ts::DateTime64(3) >= '2026-10-15 07:00:00')),
     up AS (SELECT user_id::String AS u, product_id::String AS sp, countIf(event_type::String = 'view') AS nv, countIf(event_type::String = 'purchase') AS nb
            FROM shop.history_events WHERE ts::DateTime64(3) < '2026-10-15 07:00:00'
              AND product_id::String IN (SELECT DISTINCT arrayJoin(shown::Array(String)) FROM shop.history_sessions WHERE context.page::String = 'home' AND ts::DateTime64(3) >= '2026-10-15 07:00:00')
            GROUP BY u, sp)
SELECT multiIf(up.nb > 0, '6 bought before', up.nv = 0, '0 never viewed', up.nv = 1, '1 viewed 1', up.nv = 2, '2 viewed 2', up.nv <= 4, '3 viewed 3-4', up.nv <= 9, '4 viewed 5-9', '5 viewed 10+') AS product_state,
       count() AS n, round(sum(w)) AS wsum, countIf(ck = sp) AS clicks, countIf(pu = sp) AS buys,
       round(100 * clicks / wsum, 3) AS wctr, round(100 * buys / wsum, 4) AS wconv
FROM imp LEFT JOIN up ON up.u = imp.u AND up.sp = imp.sp
GROUP BY product_state ORDER BY product_state;

-- subcategory rank inside the category (30/30)
WITH imp AS (SELECT user_id::String AS u, sh[k] AS sp, k, 1 / log2(k + 1) AS w, ck, pu
             FROM (SELECT user_id, shown::Array(String) AS sh, ifNull(clicked::String, '') AS ck, ifNull(purchased::String, '') AS pu, arrayJoin(range(1, 11)) AS k
                   FROM shop.history_sessions WHERE context.page::String = 'home' AND ts::DateTime64(3) >= '2026-10-15 07:00:00')),
     us AS (SELECT e.user_id::String AS u, c.category::String AS cat, c.subcategory::String AS sub, count() AS nv
            FROM shop.history_events e JOIN shop.catalog c ON c.product_id::String = e.product_id::String
            WHERE e.ts::DateTime64(3) < '2026-10-15 07:00:00' AND e.event_type::String = 'view' GROUP BY u, cat, sub),
     rk AS (SELECT u, sub, nv, row_number() OVER (PARTITION BY u, cat ORDER BY nv DESC, sub) AS r, sum(nv) OVER (PARTITION BY u, cat) AS catv FROM us),
     ct AS (SELECT u, cat, row_number() OVER (PARTITION BY u ORDER BY n DESC, cat) AS rc FROM (SELECT u, cat, sum(nv) AS n FROM us GROUP BY u, cat))
SELECT if(ct.rc = 1, 'A top cat', if(ct.rc = 0, 'C cat never viewed', 'B other cat')) AS cat_state,
       multiIf(rk.nv = 0, '9 never viewed sub', rk.r = 1, '1 top sub', rk.r = 2, '2 second sub', '3 3rd+ sub') AS sub_rank,
       count() AS n, round(sum(w)) AS wsum, countIf(ck = sp) AS clicks, countIf(pu = sp) AS buys,
       round(100 * clicks / wsum, 3) AS wctr, round(100 * buys / wsum, 4) AS wconv
FROM imp JOIN shop.catalog c ON c.product_id::String = imp.sp
LEFT JOIN rk ON rk.u = imp.u AND rk.sub = c.subcategory::String
LEFT JOIN ct ON ct.u = imp.u AND ct.cat = c.category::String
WHERE imp.u IN (SELECT u FROM us)
GROUP BY cat_state, sub_rank ORDER BY cat_state, sub_rank;

-- recency of category, request level, history before each request
WITH req AS (SELECT x.u AS u, x.t AS t, c.category::String AS cat, x.ck != '' AS clicked, x.pu != '' AS bought
             FROM (SELECT user_id::String AS u, ts::DateTime64(3) AS t, (shown::Array(String))[1] AS s1, ifNull(clicked::String, '') AS ck, ifNull(purchased::String, '') AS pu
                   FROM shop.history_sessions WHERE context.page::String = 'home' AND ts::DateTime64(3) >= '2026-10-15 07:00:00') x
             JOIN shop.catalog c ON c.product_id::String = x.s1),
     ev AS (SELECT e.user_id::String AS u, c.category::String AS cat, e.ts::DateTime64(3) AS t
            FROM shop.history_events e JOIN shop.catalog c ON c.product_id::String = e.product_id::String
            WHERE e.event_type::String = 'view' AND e.user_id::String IN (SELECT user_id::String FROM shop.history_sessions WHERE context.page::String = 'home' AND ts::DateTime64(3) >= '2026-10-15 07:00:00'))
SELECT multiIf(ev.t = toDateTime64('1970-01-01 00:00:00', 3), '9 never', dateDiff('second', ev.t, req.t) < 2 * 86400, '1 0-1 d', dateDiff('second', ev.t, req.t) < 8 * 86400, '2 2-7 d', dateDiff('second', ev.t, req.t) < 31 * 86400, '3 8-30 d', '4 31+ d') AS cat_last_view,
       count() AS requests, countIf(clicked) AS clicks, countIf(bought) AS buys, round(100 * clicks / requests, 3) AS ctr, round(100 * buys / requests, 3) AS conv
FROM req ASOF LEFT JOIN ev ON ev.u = req.u AND ev.cat = req.cat AND ev.t < req.t
GROUP BY cat_last_view ORDER BY cat_last_view;

-- recency of category within top or other category (top from the first 30 days), before each request
WITH req AS (SELECT x.u AS u, x.t AS t, c.category::String AS cat, x.ck != '' AS clicked, x.pu != '' AS bought
             FROM (SELECT user_id::String AS u, ts::DateTime64(3) AS t, (shown::Array(String))[1] AS s1, ifNull(clicked::String, '') AS ck, ifNull(purchased::String, '') AS pu
                   FROM shop.history_sessions WHERE context.page::String = 'home' AND ts::DateTime64(3) >= '2026-10-15 07:00:00') x
             JOIN shop.catalog c ON c.product_id::String = x.s1),
     ev AS (SELECT e.user_id::String AS u, c.category::String AS cat, e.ts::DateTime64(3) AS t
            FROM shop.history_events e JOIN shop.catalog c ON c.product_id::String = e.product_id::String
            WHERE e.event_type::String = 'view' AND e.user_id::String IN (SELECT user_id::String FROM shop.history_sessions WHERE context.page::String = 'home' AND ts::DateTime64(3) >= '2026-10-15 07:00:00')),
     top AS (SELECT u, argMax(cat, n) AS tc FROM (SELECT e.user_id::String AS u, c.category::String AS cat, count() AS n FROM shop.history_events e JOIN shop.catalog c ON c.product_id::String = e.product_id::String
             WHERE e.event_type::String = 'view' AND e.ts::DateTime64(3) < '2026-10-15 07:00:00' GROUP BY u, cat) GROUP BY u),
     j AS (SELECT req.u AS u, req.cat AS cat, req.clicked AS clicked, req.bought AS bought, multiIf(ev.t = toDateTime64('1970-01-01 00:00:00', 3), '9 never', dateDiff('second', ev.t, req.t) < 2 * 86400, '1 0-1 d', dateDiff('second', ev.t, req.t) < 8 * 86400, '2 2-7 d', dateDiff('second', ev.t, req.t) < 31 * 86400, '3 8-30 d', '4 31+ d') AS rec
           FROM req ASOF LEFT JOIN ev ON ev.u = req.u AND ev.cat = req.cat AND ev.t < req.t)
SELECT if(top.tc = j.cat, 'top cat', 'other cat') AS cat_state, rec AS cat_last_view, count() AS requests, countIf(clicked) AS clicks, countIf(bought) AS buys, round(100 * clicks / requests, 3) AS ctr, round(100 * buys / requests, 3) AS conv
FROM j LEFT JOIN top ON top.u = j.u
GROUP BY cat_state, cat_last_view ORDER BY cat_state, cat_last_view;

-- recency of product view, split by bought before the request, before each request
WITH imp AS (SELECT user_id::String AS u, ts::DateTime64(3) AS t, sh[k] AS sp, 1 / log2(k + 1) AS w, ck, pu
             FROM (SELECT user_id, ts, shown::Array(String) AS sh, ifNull(clicked::String, '') AS ck, ifNull(purchased::String, '') AS pu, arrayJoin(range(1, 11)) AS k
                   FROM shop.history_sessions WHERE context.page::String = 'home' AND ts::DateTime64(3) >= '2026-10-15 07:00:00')),
     pids AS (SELECT DISTINCT arrayJoin(shown::Array(String)) AS p FROM shop.history_sessions WHERE context.page::String = 'home' AND ts::DateTime64(3) >= '2026-10-15 07:00:00'),
     ev AS (SELECT user_id::String AS u, product_id::String AS sp, ts::DateTime64(3) AS t FROM shop.history_events WHERE event_type::String = 'view' AND product_id::String IN (SELECT p FROM pids)),
     fb AS (SELECT user_id::String AS u, product_id::String AS sp, min(ts::DateTime64(3)) AS tb FROM shop.history_events WHERE event_type::String = 'purchase' AND product_id::String IN (SELECT p FROM pids) GROUP BY u, sp),
     j AS (SELECT imp.u AS u, imp.sp AS sp, imp.t AS t, imp.w AS w, imp.ck AS ck, imp.pu AS pu, ev.t AS tv FROM imp ASOF LEFT JOIN ev ON ev.u = imp.u AND ev.sp = imp.sp AND ev.t < imp.t)
SELECT if(fb.tb != toDateTime64('1970-01-01 00:00:00', 3) AND fb.tb < j.t, 'bought before', 'not bought before') AS bought,
       multiIf(tv = toDateTime64('1970-01-01 00:00:00', 3), '9 never viewed', dateDiff('second', tv, t) < 2 * 86400, '1 0-1 d', dateDiff('second', tv, t) < 8 * 86400, '2 2-7 d', dateDiff('second', tv, t) < 31 * 86400, '3 8-30 d', '4 31+ d') AS product_last_view,
       count() AS n, round(sum(w)) AS wsum, countIf(ck = sp) AS clicks, countIf(pu = sp) AS buys, round(100 * clicks / wsum, 3) AS wctr, round(100 * buys / wsum, 4) AS wconv
FROM j LEFT JOIN fb ON fb.u = j.u AND fb.sp = j.sp
GROUP BY bought, product_last_view ORDER BY bought, product_last_view;

-- live home returning: category view rank
WITH imp AS (SELECT u, sh[k] AS sp, 1 / log2(k + 1) AS w, ck, pu
             FROM (SELECT r.user_id::String AS u, f.shown::Array(String) AS sh, f.clicked::String AS ck, f.purchased::String AS pu, arrayJoin(range(1, 11)) AS k
                   FROM {TEAM}.feedback f JOIN shop.requests r ON r.request_id::String = f.request_id::String WHERE r.context.page::String = 'home' AND NOT r.is_new_user::Bool)),
     uc AS (SELECT e.user_id::String AS u, c.category::String AS cat, count() AS nv FROM shop.history_events e JOIN shop.catalog c ON c.product_id::String = e.product_id::String
            WHERE e.event_type::String = 'view' AND e.user_id::String IN (SELECT u FROM imp) GROUP BY u, cat),
     rk AS (SELECT u, cat, nv, row_number() OVER (PARTITION BY u ORDER BY nv DESC, cat) AS rv, nv / sum(nv) OVER (PARTITION BY u) AS s FROM uc)
SELECT multiIf(rk.nv = 0, '5 never viewed cat', rk.rv = 1, '1 top', rk.rv = 2, '2 second', rk.rv = 3, '3 third', '4 4th+') AS view_rank,
       count() AS n, round(sum(w)) AS wsum, countIf(ck = sp) AS clicks, countIf(pu = sp) AS buys, round(100 * clicks / wsum, 3) AS wctr, round(100 * buys / wsum, 4) AS wconv
FROM imp JOIN shop.catalog c ON c.product_id::String = imp.sp LEFT JOIN rk ON rk.u = imp.u AND rk.cat = c.category::String
GROUP BY view_rank ORDER BY view_rank;

-- live home returning: category share bucket
WITH imp AS (SELECT u, sh[k] AS sp, 1 / log2(k + 1) AS w, ck, pu
             FROM (SELECT r.user_id::String AS u, f.shown::Array(String) AS sh, f.clicked::String AS ck, f.purchased::String AS pu, arrayJoin(range(1, 11)) AS k
                   FROM {TEAM}.feedback f JOIN shop.requests r ON r.request_id::String = f.request_id::String WHERE r.context.page::String = 'home' AND NOT r.is_new_user::Bool)),
     uc AS (SELECT e.user_id::String AS u, c.category::String AS cat, count() AS nv FROM shop.history_events e JOIN shop.catalog c ON c.product_id::String = e.product_id::String
            WHERE e.event_type::String = 'view' AND e.user_id::String IN (SELECT u FROM imp) GROUP BY u, cat),
     rk AS (SELECT u, cat, nv / sum(nv) OVER (PARTITION BY u) AS s FROM uc)
SELECT multiIf(rk.s = 0, '0 none', rk.s < 0.05, '1 <5%', rk.s < 0.15, '2 5-15%', rk.s < 0.3, '3 15-30%', '4 30%+') AS share,
       count() AS n, round(sum(w)) AS wsum, countIf(ck = sp) AS clicks, countIf(pu = sp) AS buys, round(100 * clicks / wsum, 3) AS wctr, round(100 * buys / wsum, 4) AS wconv
FROM imp JOIN shop.catalog c ON c.product_id::String = imp.sp LEFT JOIN rk ON rk.u = imp.u AND rk.cat = c.category::String
GROUP BY share ORDER BY share;

-- live home returning: product state
WITH imp AS (SELECT u, sh[k] AS sp, 1 / log2(k + 1) AS w, ck, pu
             FROM (SELECT r.user_id::String AS u, f.shown::Array(String) AS sh, f.clicked::String AS ck, f.purchased::String AS pu, arrayJoin(range(1, 11)) AS k
                   FROM {TEAM}.feedback f JOIN shop.requests r ON r.request_id::String = f.request_id::String WHERE r.context.page::String = 'home' AND NOT r.is_new_user::Bool)),
     up AS (SELECT user_id::String AS u, product_id::String AS sp, countIf(event_type::String = 'view') AS nv, countIf(event_type::String = 'purchase') AS nb FROM shop.history_events
            WHERE user_id::String IN (SELECT u FROM imp) GROUP BY u, sp)
SELECT multiIf(up.nb > 0, '3 bought before', up.nv > 0, '2 viewed not bought', '1 never seen') AS product_state,
       count() AS n, round(sum(w)) AS wsum, countIf(ck = sp) AS clicks, countIf(pu = sp) AS buys, round(100 * clicks / wsum, 3) AS wctr, round(100 * buys / wsum, 4) AS wconv
FROM imp LEFT JOIN up ON up.u = imp.u AND up.sp = imp.sp
GROUP BY product_state ORDER BY product_state;

-- live home: outcome by model version and new shopper
SELECT s.model_version::String AS mv, count() AS n, countIf(f.clicked::String != '') AS clicks, countIf(f.purchased::String != '') AS buys, round(100 * buys / n, 3) AS conv
FROM {TEAM}.feedback f JOIN shop.requests r ON r.request_id::String = f.request_id::String LEFT JOIN {TEAM}.submissions s ON s.request_id::String = f.request_id::String
WHERE r.context.page::String = 'home' GROUP BY mv, r.is_new_user::Bool AS new ORDER BY mv, new;

-- live new shoppers on home: today's organic events before the request, by product category share and product state
WITH imp AS (SELECT u, t0, sh[k] AS sp, 1 / log2(k + 1) AS w, ck, pu
             FROM (SELECT r.user_id::String AS u, r.ts::DateTime64(3) AS t0, f.shown::Array(String) AS sh, f.clicked::String AS ck, f.purchased::String AS pu, arrayJoin(range(1, 11)) AS k
                   FROM {TEAM}.feedback f JOIN shop.requests r ON r.request_id::String = f.request_id::String WHERE r.context.page::String = 'home' AND r.is_new_user::Bool)),
     ev AS (SELECT e.user_id::String AS u, e.ts::DateTime64(3) AS t, e.product_id::String AS p, e.event_type::String AS et, c.category::String AS cat
            FROM shop.events e JOIN shop.catalog c ON c.product_id::String = e.product_id::String WHERE e.user_id::String IN (SELECT u FROM imp)),
     j AS (SELECT imp.u AS u, imp.t0 AS t0, imp.sp AS sp, imp.w AS w, imp.ck AS ck, imp.pu AS pu, c.category::String AS cat FROM imp JOIN shop.catalog c ON c.product_id::String = imp.sp),
     agg AS (SELECT j.u AS u, j.t0 AS t0, j.sp AS sp, any(j.w) AS w, any(j.ck) AS ck, any(j.pu) AS pu,
                    countIf(ev.t < j.t0 AND ev.et = 'view') AS nv_all, countIf(ev.t < j.t0 AND ev.et = 'view' AND ev.cat = j.cat) AS nv_cat,
                    countIf(ev.t < j.t0 AND ev.et = 'view' AND ev.p = j.sp) AS nv_p, countIf(ev.t < j.t0 AND ev.et = 'purchase' AND ev.p = j.sp) AS nb_p
             FROM j LEFT JOIN ev ON ev.u = j.u GROUP BY j.u, j.t0, j.sp)
SELECT multiIf(nv_all = 0, '0 no events today', nb_p > 0, '5 bought today', nv_p > 0, '4 product viewed today', nv_cat / nv_all >= 0.3, '3 cat share 30%+', nv_cat > 0, '2 cat share >0', '1 cat not viewed today') AS state,
       count() AS n, round(sum(w)) AS wsum, countIf(ck = sp) AS clicks, countIf(pu = sp) AS buys, round(100 * clicks / wsum, 3) AS wctr, round(100 * buys / wsum, 3) AS wconv
FROM agg GROUP BY state ORDER BY state;
