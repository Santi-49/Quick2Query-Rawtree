-- H-home-ceiling: what shoppers with no recent views (home page) click and buy, live first, history as support.
-- Rates per slot-weighted impression: wconv = purchases / sum of 1/log2(slot+1), in %. Live = team_01.feedback of 14 Nov up to ~16:20 UTC.

-- live home: product class x shopper type
WITH imp AS (SELECT r.u AS u, r.nu AS nu, r.t AS t, f.sh[k] AS sp, 1 / log2(k + 1) AS w, f.ck AS ck, f.pu AS pu
             FROM (SELECT request_id::String AS id, shown::Array(String) AS sh, clicked::String AS ck, purchased::String AS pu, arrayJoin(range(1, 11)) AS k FROM {TEAM}.feedback) f
             JOIN (SELECT request_id::String AS id, user_id::String AS u, is_new_user::Bool AS nu, ts::DateTime64(3) AS t FROM shop.requests WHERE length(recent_views::Array(JSON)) = 0) r ON r.id = f.id),
     cat AS (SELECT product_id::String AS p, category::String AS cat, subcategory::String AS sub, brand::String AS br FROM shop.catalog
             UNION ALL SELECT product_id::String, any(category::String), any(subcategory::String), any(brand::String) FROM shop.catalog_updates WHERE change::String = 'new_product' GROUP BY product_id::String),
     he AS (SELECT e.user_id::String AS u, e.product_id::String AS p, e.event_type::String AS et, e.ts::DateTime64(3) AS t, c.cat AS cat, c.sub AS sub, c.br AS br
            FROM shop.history_events e JOIN cat c ON c.p = e.product_id::String WHERE e.user_id::String IN (SELECT DISTINCT u FROM imp WHERE NOT nu)),
     up AS (SELECT u, p, countIf(et = 'view') AS nv, countIf(et = 'add_to_cart') AS nc, countIf(et = 'purchase') AS nb FROM he GROUP BY u, p),
     rk AS (SELECT u, cat, row_number() OVER (PARTITION BY u ORDER BY n DESC, cat) AS r FROM (SELECT u, cat, countIf(et = 'view') AS n FROM he GROUP BY u, cat)),
     te AS (SELECT user_id::String AS u, product_id::String AS p, min(ts::DateTime64(3)) AS t0 FROM shop.events WHERE event_type::String = 'view' AND user_id::String IN (SELECT DISTINCT u FROM imp) GROUP BY u, p)
SELECT nu AS new_user,
       multiIf(up.nb > 0, '1 bought in history', te.t0 > '2000-01-01' AND te.t0 < imp.t, '2 viewed today before', up.nc > 0, '3 cart not bought', up.nv > 0, '4 viewed not bought', rk.r = 1, '5 top cat', rk.r IN (2, 3), '6 cat 2-3', rk.r > 3, '7 cat 4+', '8 no history') AS cls,
       count() AS n, round(sum(w)) AS wsum, countIf(ck = sp) AS clicks, countIf(pu = sp) AS buys, round(100 * clicks / wsum, 3) AS wctr, round(100 * buys / wsum, 4) AS wconv
FROM imp JOIN cat c ON c.p = imp.sp
LEFT JOIN up ON up.u = imp.u AND up.p = imp.sp LEFT JOIN rk ON rk.u = imp.u AND rk.cat = c.cat LEFT JOIN te ON te.u = imp.u AND te.p = imp.sp
GROUP BY new_user, cls ORDER BY new_user, cls;

-- live home: category of shown product vs today's views before request (any shopper)
WITH imp AS (SELECT r.u AS u, r.nu AS nu, r.t AS t, f.sh[k] AS sp, 1 / log2(k + 1) AS w, f.ck AS ck, f.pu AS pu
             FROM (SELECT request_id::String AS id, shown::Array(String) AS sh, clicked::String AS ck, purchased::String AS pu, arrayJoin(range(1, 11)) AS k FROM {TEAM}.feedback) f
             JOIN (SELECT request_id::String AS id, user_id::String AS u, is_new_user::Bool AS nu, ts::DateTime64(3) AS t FROM shop.requests WHERE length(recent_views::Array(JSON)) = 0) r ON r.id = f.id),
     cat AS (SELECT product_id::String AS p, category::String AS cat, subcategory::String AS sub FROM shop.catalog
             UNION ALL SELECT product_id::String, any(category::String), any(subcategory::String) FROM shop.catalog_updates WHERE change::String = 'new_product' GROUP BY product_id::String),
     te AS (SELECT e.user_id::String AS u, e.ts::DateTime64(3) AS t, c.cat AS cat, c.sub AS sub FROM shop.events e JOIN cat c ON c.p = e.product_id::String
            WHERE e.event_type::String = 'view' AND e.user_id::String IN (SELECT DISTINCT u FROM imp)),
     tc AS (SELECT u, cat, min(t) AS t0, max(t) AS t1 FROM te GROUP BY u, cat),
     ts AS (SELECT u, sub, min(t) AS t0 FROM te GROUP BY u, sub),
     tl AS (SELECT u, groupArray((t, cat)) AS a FROM te GROUP BY u)
SELECT nu AS new_user,
       multiIf(ts.t0 > '2000-01-01' AND ts.t0 < imp.t, '1 sub viewed today', tc.t0 > '2000-01-01' AND tc.t0 < imp.t, '2 cat viewed today', arrayExists(x -> x.1 < imp.t, tl.a), '3 other cat today', '4 no views today before') AS today,
       count() AS n, round(sum(w)) AS wsum, countIf(ck = sp) AS clicks, countIf(pu = sp) AS buys, round(100 * clicks / wsum, 3) AS wctr, round(100 * buys / wsum, 4) AS wconv
FROM imp JOIN cat c ON c.p = imp.sp
LEFT JOIN tc ON tc.u = imp.u AND tc.cat = c.cat LEFT JOIN ts ON ts.u = imp.u AND ts.sub = c.sub LEFT JOIN tl ON tl.u = imp.u
GROUP BY new_user, today ORDER BY new_user, today;

-- live home: requests with earlier views today, share
SELECT r.nu AS new_user, count() AS requests, countIf(arrayCount(x -> x < r.t, e.ts) > 0) AS with_views_today, round(with_views_today / requests, 3) AS share,
       countIf(r.fb AND arrayCount(x -> x < r.t, e.ts) > 0) AS buys_with, countIf(r.fb AND arrayCount(x -> x < r.t, e.ts) = 0) AS buys_without
FROM (SELECT rq.request_id::String AS id, rq.user_id::String AS u, rq.is_new_user::Bool AS nu, rq.ts::DateTime64(3) AS t, f.pu != '' AS fb FROM shop.requests rq
      JOIN (SELECT request_id::String AS id, purchased::String AS pu FROM {TEAM}.feedback) f ON f.id = rq.request_id::String WHERE length(rq.recent_views::Array(JSON)) = 0) r
LEFT JOIN (SELECT user_id::String AS u, groupArray(ts::DateTime64(3)) AS ts FROM shop.events WHERE event_type::String = 'view' GROUP BY u) e ON e.u = r.u
GROUP BY new_user;

-- live all pages: shown product not in recent views, history relation incl. carts and view counts
WITH imp AS (SELECT r.u AS u, r.home AS home, f.sh[k] AS sp, 1 / log2(k + 1) AS w, f.ck AS ck, f.pu AS pu
             FROM (SELECT request_id::String AS id, shown::Array(String) AS sh, clicked::String AS ck, purchased::String AS pu, arrayJoin(range(1, 11)) AS k FROM {TEAM}.feedback) f
             JOIN (SELECT request_id::String AS id, user_id::String AS u, length(recent_views::Array(JSON)) = 0 AS home, arrayMap(v -> v.product_id::String, recent_views::Array(JSON)) AS rv FROM shop.requests WHERE NOT is_new_user::Bool) r ON r.id = f.id
             WHERE NOT has(r.rv, f.sh[k])),
     up AS (SELECT user_id::String AS u, product_id::String AS p, countIf(event_type::String = 'view') AS nv, countIf(event_type::String = 'add_to_cart') AS nc, countIf(event_type::String = 'purchase') AS nb
            FROM shop.history_events WHERE user_id::String IN (SELECT DISTINCT u FROM imp) GROUP BY u, p)
SELECT home, multiIf(up.nb > 0, '0 bought', up.nc >= 2, '1 cart 2+', up.nc = 1, '2 cart 1', up.nv >= 3, '3 viewed 3+', up.nv = 2, '4 viewed 2', up.nv = 1, '5 viewed 1', '6 never') AS cls,
       count() AS n, round(sum(w)) AS wsum, countIf(ck = sp) AS clicks, countIf(pu = sp) AS buys, round(100 * clicks / wsum, 3) AS wctr, round(100 * buys / wsum, 4) AS wconv
FROM imp LEFT JOIN up ON up.u = imp.u AND up.p = imp.sp
GROUP BY home, cls ORDER BY home, cls;

-- history home: cart-not-bought vs viewed-not-bought (30/30)
WITH imp AS (SELECT user_id::String AS u, sh[k] AS sp, 1 / log2(k + 1) AS w, ck, pu
             FROM (SELECT user_id, shown::Array(String) AS sh, ifNull(clicked::String, '') AS ck, ifNull(purchased::String, '') AS pu, arrayJoin(range(1, 11)) AS k
                   FROM shop.history_sessions WHERE context.page::String = 'home' AND ts::DateTime64(3) >= '2026-10-15 07:00:00')),
     up AS (SELECT user_id::String AS u, product_id::String AS p, countIf(event_type::String = 'view') AS nv, countIf(event_type::String = 'add_to_cart') AS nc, countIf(event_type::String = 'purchase') AS nb
            FROM shop.history_events WHERE ts::DateTime64(3) < '2026-10-15 07:00:00' AND product_id::String IN (SELECT DISTINCT sp FROM imp) GROUP BY u, p)
SELECT multiIf(up.nb > 0, '0 bought', up.nc > 0, '1 cart not bought', up.nv >= 2, '2 viewed 2+', up.nv = 1, '3 viewed 1', '4 never') AS cls,
       count() AS n, round(sum(w)) AS wsum, countIf(ck = sp) AS clicks, countIf(pu = sp) AS buys, round(100 * clicks / wsum, 3) AS wctr, round(100 * buys / wsum, 4) AS wconv
FROM imp LEFT JOIN up ON up.u = imp.u AND up.p = imp.sp
GROUP BY cls ORDER BY cls;

-- coverage: cart-not-bought products per returning shopper (all history)
SELECT count() AS users, countIf(n > 0) AS with_cart, round(with_cart / users, 3) AS share, quantiles(0.25, 0.5, 0.75, 0.9)(n) AS per_user
FROM (SELECT u, countIf(nc > 0 AND nb = 0) AS n FROM (SELECT user_id::String AS u, product_id::String AS p, countIf(event_type::String = 'add_to_cart') AS nc, countIf(event_type::String = 'purchase') AS nb FROM shop.history_events GROUP BY u, p) GROUP BY u);

-- carts vs views: how many viewed-not-bought products were carted, by view count
SELECT least(nv, 5) AS views, count() AS pairs, countIf(nc > 0) AS carted, round(carted / pairs, 3) AS share
FROM (SELECT user_id::String AS u, product_id::String AS p, countIf(event_type::String = 'view') AS nv, countIf(event_type::String = 'add_to_cart') AS nc, countIf(event_type::String = 'purchase') AS nb FROM shop.history_events WHERE cityHash64(user_id::String) % 8 = 0 GROUP BY u, p)
WHERE nb = 0 GROUP BY views ORDER BY views;

-- live home: first organic view and purchase after the request, hit rates of simple top-10 lists
WITH cat AS (SELECT product_id::String AS p, category::String AS cat, subcategory::String AS sub FROM shop.catalog
             UNION ALL SELECT product_id::String, any(category::String), any(subcategory::String) FROM shop.catalog_updates WHERE change::String = 'new_product' GROUP BY product_id::String),
     hr AS (SELECT request_id::String AS id, user_id::String AS u, is_new_user::Bool AS nu, ts::DateTime64(3) AS t, context.device::String AS dev, context.region::String AS reg
            FROM shop.requests WHERE length(recent_views::Array(JSON)) = 0 AND ts::DateTime64(3) < (SELECT max(ts::DateTime64(3)) FROM shop.events) - INTERVAL 10 MINUTE),
     le AS (SELECT user_id::String AS u, ts::DateTime64(3) AS t, product_id::String AS p, event_type::String AS et FROM shop.events WHERE user_id::String IN (SELECT DISTINCT u FROM hr)),
     nx AS (SELECT hr.id AS id, argMinIf(le.p, le.t, le.t >= hr.t AND le.t < hr.t + INTERVAL 10 MINUTE AND le.et = 'view') AS fv,
                   argMinIf(le.p, le.t, le.t >= hr.t AND le.t < hr.t + INTERVAL 10 MINUTE AND le.et = 'purchase') AS fb,
                   argMaxIf(le.p, le.t, le.t < hr.t AND le.et = 'view') AS today_last,
                   groupUniqArrayIf(le.p, le.t < hr.t AND le.et = 'add_to_cart') AS today_cart,
                   groupUniqArrayIf(le.p, le.t < hr.t AND le.et = 'view') AS today_viewed
            FROM hr LEFT JOIN le ON le.u = hr.u GROUP BY hr.id),
     he AS (SELECT e.user_id::String AS u, e.ts::DateTime64(3) AS t, e.product_id::String AS p, e.event_type::String AS et, c.cat AS cat, c.sub AS sub
            FROM shop.history_events e JOIN cat c ON c.p = e.product_id::String WHERE e.user_id::String IN (SELECT DISTINCT u FROM hr WHERE NOT nu)),
     hp AS (SELECT u, p, any(cat) AS cat, any(sub) AS sub, countIf(et = 'view') AS nv, countIf(et = 'add_to_cart') AS nc, countIf(et = 'purchase') AS nb, max(t) AS last FROM he GROUP BY u, p),
     prof AS (SELECT u, argMax(cat, nv) AS dummy, arraySlice(arrayMap(x -> x.2, arrayReverseSort(groupArrayIf((last, p), nc > 0 AND nb = 0))), 1, 10) AS carts,
                     arraySlice(arrayMap(x -> x.2, arrayReverseSort(groupArrayIf((last, p), nv > 0 AND nb = 0))), 1, 10) AS recent10,
                     argMax(sub, last) AS last_sub, argMax(cat, last) AS last_cat, argMaxIf(sub, last, nb > 0) AS buy_sub
              FROM hp GROUP BY u),
     topc AS (SELECT u, argMax(cat, n) AS top_cat, argMax(sub, n2) AS top_sub FROM (SELECT u, cat, sub, sum(nv) OVER (PARTITION BY u, cat) AS n, sum(nv) OVER (PARTITION BY u, sub) AS n2 FROM hp) GROUP BY u),
     ps AS (SELECT product_id::String AS p, countIf(event_type::String = 'purchase') AS nb FROM shop.history_events GROUP BY p),
     bsc AS (SELECT c.cat AS cat, arraySlice(arrayMap(x -> x.2, arrayReverseSort(groupArray((ps.nb, ps.p)))), 1, 10) AS l FROM ps JOIN cat c ON c.p = ps.p GROUP BY cat),
     bss AS (SELECT c.sub AS sub, arraySlice(arrayMap(x -> x.2, arrayReverseSort(groupArray((ps.nb, ps.p)))), 1, 10) AS l FROM ps JOIN cat c ON c.p = ps.p GROUP BY sub),
     g AS (SELECT arraySlice(arrayMap(x -> x.2, arrayReverseSort(groupArray((nb, p)))), 1, 10) AS l FROM ps),
     seg AS (SELECT dev, reg, arraySlice(arrayMap(x -> x.2, arrayReverseSort(groupArray((n, p)))), 1, 10) AS l
             FROM (SELECT device::String AS dev, region::String AS reg, product_id::String AS p, count() AS n FROM shop.history_events WHERE event_type::String = 'purchase' GROUP BY dev, reg, p) GROUP BY dev, reg),
     hb AS (SELECT h, arraySlice(arrayMap(x -> x.2, arrayReverseSort(groupArray((nb, p)))), 1, 10) AS lb, arraySlice(arrayMap(x -> x.2, arrayReverseSort(groupArray((nv, p)))), 1, 10) AS lv
            FROM (SELECT toStartOfHour(ts::DateTime64(3)) + INTERVAL 1 HOUR AS h, product_id::String AS p, countIf(event_type::String = 'purchase') AS nb, countIf(event_type::String = 'view') AS nv FROM shop.events GROUP BY h, p) GROUP BY h),
     x AS (SELECT hr.nu AS nu, nx.fv AS fv, nx.fb AS fb, cv.cat AS fv_cat, cv.sub AS fv_sub, prof.carts AS carts, prof.recent10 AS recent10, topc.top_cat AS top_cat, topc.top_sub AS top_sub, prof.last_sub AS last_sub, prof.last_cat AS last_cat, prof.buy_sub AS buy_sub,
                  bsc.l AS l_topcat, bss.l AS l_lastsub, bsb.l AS l_buysub, g.l AS l_global, seg.l AS l_seg, hb.lb AS l_hourbuy, hb.lv AS l_hourview, nx.today_cart AS today_cart, nx.today_viewed AS today_viewed, ct.sub AS today_sub, tl.l AS l_todaysub,
                  prof.u != '' AS hist
           FROM hr JOIN nx ON nx.id = hr.id LEFT JOIN cat cv ON cv.p = nx.fv LEFT JOIN prof ON prof.u = hr.u LEFT JOIN topc ON topc.u = hr.u
           LEFT JOIN bsc ON bsc.cat = topc.top_cat LEFT JOIN bss ON bss.sub = prof.last_sub LEFT JOIN bss bsb ON bsb.sub = prof.buy_sub CROSS JOIN g LEFT JOIN seg ON seg.dev = hr.dev AND seg.reg = hr.reg
           LEFT JOIN hb ON hb.h = toStartOfHour(hr.t) LEFT JOIN cat ct ON ct.p = nx.today_last LEFT JOIN bss tl ON tl.sub = ct.sub)
SELECT nu AS new_user, count() AS requests, countIf(fv != '') AS with_view_10m, countIf(fb != '') AS with_buy_10m,
       countIf(fv != '' AND fv_cat = top_cat) AS v_cat_is_topcat, countIf(fv != '' AND fv_cat = last_cat) AS v_cat_is_last_hist_cat, countIf(fv != '' AND fv_sub = last_sub) AS v_sub_is_last_hist_sub, countIf(fv != '' AND fv_sub = top_sub) AS v_sub_is_top_sub,
       countIf(fv != '' AND fv_sub = today_sub) AS v_sub_is_today_last_sub,
       countIf(has(carts, fv)) AS v_in_carts, countIf(has(recent10, fv)) AS v_in_recent10_hist, countIf(has(today_viewed, fv)) AS v_viewed_today, countIf(has(today_cart, fv)) AS v_carted_today,
       countIf(has(l_topcat, fv)) AS v_in_topcat_best10, countIf(has(l_lastsub, fv)) AS v_in_lastsub_best10, countIf(has(l_buysub, fv)) AS v_in_buysub_best10, countIf(has(l_global, fv)) AS v_in_global_best10,
       countIf(has(l_seg, fv)) AS v_in_segment_best10, countIf(has(l_hourbuy, fv)) AS v_in_prev_hour_buys10, countIf(has(l_hourview, fv)) AS v_in_prev_hour_views10, countIf(has(l_todaysub, fv)) AS v_in_today_sub_best10,
       countIf(has(carts, fb)) AS b_in_carts, countIf(has(today_viewed, fb)) AS b_viewed_today, countIf(has(today_cart, fb)) AS b_carted_today, countIf(has(recent10, fb)) AS b_in_recent10_hist,
       countIf(has(l_topcat, fb)) AS b_in_topcat_best10, countIf(has(l_global, fb)) AS b_in_global_best10, countIf(has(l_seg, fb)) AS b_in_segment_best10, countIf(has(l_hourbuy, fb)) AS b_in_prev_hour_buys10, countIf(has(l_todaysub, fb)) AS b_in_today_sub_best10
FROM x GROUP BY new_user ORDER BY new_user;

-- new shoppers today: organic purchases and views caught by top-10 / top-50 lists (all-time, segment, live previous hour, live today so far)
WITH nu AS (SELECT DISTINCT user_id::String AS u FROM shop.requests WHERE is_new_user::Bool),
     ev AS (SELECT user_id::String AS u, product_id::String AS p, event_type::String AS et, ts::DateTime64(3) AS t, device::String AS dev, region::String AS reg, toStartOfHour(ts::DateTime64(3)) AS h
            FROM shop.events WHERE user_id::String IN (SELECT u FROM nu) AND event_type::String IN ('view', 'purchase')),
     ps AS (SELECT product_id::String AS p, countIf(event_type::String = 'purchase') AS nb FROM shop.history_events GROUP BY p),
     g AS (SELECT arrayMap(x -> x.2, arrayReverseSort(groupArray((nb, p)))) AS l FROM ps),
     seg AS (SELECT dev, reg, arrayMap(x -> x.2, arrayReverseSort(groupArray((n, p)))) AS l
             FROM (SELECT device::String AS dev, region::String AS reg, product_id::String AS p, count() AS n FROM shop.history_events WHERE event_type::String = 'purchase' GROUP BY dev, reg, p) GROUP BY dev, reg),
     lh AS (SELECT h, arrayMap(x -> x.2, arrayReverseSort(groupArray((nb, p)))) AS l
            FROM (SELECT toStartOfHour(ts::DateTime64(3)) + INTERVAL 1 HOUR AS h, product_id::String AS p, countIf(event_type::String = 'purchase') AS nb FROM shop.events GROUP BY h, p HAVING nb > 0) GROUP BY h),
     hrs AS (SELECT DISTINCT toStartOfHour(ts::DateTime64(3)) AS h FROM shop.events),
     lc AS (SELECT hrs.h AS h, arrayMap(x -> x.2, arrayReverseSort(groupArray((d.nb, d.p)))) AS l
            FROM hrs JOIN (SELECT toStartOfHour(ts::DateTime64(3)) AS hh, product_id::String AS p, countIf(event_type::String = 'purchase') AS nb FROM shop.events GROUP BY hh, p) d ON 1 = 1
            WHERE d.hh < hrs.h GROUP BY hrs.h),
     x AS (SELECT ev.et AS et, ev.p AS p, g.l AS lg, seg.l AS ls, lh.l AS lh, lc.l AS lc FROM ev CROSS JOIN g LEFT JOIN seg ON seg.dev = ev.dev AND seg.reg = ev.reg LEFT JOIN lh ON lh.h = ev.h LEFT JOIN lc ON lc.h = ev.h WHERE ev.h > (SELECT min(h) FROM hrs))
SELECT et, count() AS n,
       round(countIf(has(arraySlice(lg, 1, 10), p)) / n, 4) AS alltime10, round(countIf(has(arraySlice(lg, 1, 50), p)) / n, 4) AS alltime50,
       round(countIf(has(arraySlice(ls, 1, 10), p)) / n, 4) AS segment10, round(countIf(has(arraySlice(ls, 1, 50), p)) / n, 4) AS segment50,
       round(countIf(has(arraySlice(lh, 1, 10), p)) / n, 4) AS prev_hour10, round(countIf(has(arraySlice(lh, 1, 50), p)) / n, 4) AS prev_hour50,
       round(countIf(has(arraySlice(lc, 1, 10), p)) / n, 4) AS today10, round(countIf(has(arraySlice(lc, 1, 50), p)) / n, 4) AS today50
FROM x GROUP BY et;

-- new shoppers, home: what they clicked in our carousel
SELECT f.mv AS mv, f.k AS slot, f.ck AS clicked, f.ck = f.pu AS bought, c.category::String AS cat, c.subcategory::String AS sub, r.dev AS dev, r.reg AS reg, indexOf(g.l, f.ck) AS alltime_rank
FROM (SELECT fb.request_id::String AS id, fb.clicked::String AS ck, fb.purchased::String AS pu, indexOf(fb.shown::Array(String), fb.clicked::String) AS k, s.mv AS mv FROM {TEAM}.feedback fb
      LEFT JOIN (SELECT request_id::String AS id, any(model_version::String) AS mv FROM {TEAM}.submissions GROUP BY id) s ON s.id = fb.request_id::String WHERE fb.clicked::String != '') f
JOIN (SELECT request_id::String AS id, context.device::String AS dev, context.region::String AS reg FROM shop.requests WHERE is_new_user::Bool AND length(recent_views::Array(JSON)) = 0) r ON r.id = f.id
LEFT JOIN shop.catalog c ON c.product_id::String = f.ck
CROSS JOIN (SELECT arrayMap(x -> x.2, arrayReverseSort(groupArray((nb, p)))) AS l FROM (SELECT product_id::String AS p, countIf(event_type::String = 'purchase') AS nb FROM shop.history_events GROUP BY p)) g
ORDER BY bought DESC, cat;

-- new shoppers today: first view category share by segment group and 4-hour block
SELECT multiIf(dev = 'android' AND reg IN ('Andalucía', 'Canarias', 'Murcia'), '1 android-south', dev = 'android', '2 android-other', dev = 'ios', '3 ios', '4 web') AS seg, intDiv(toHour(t), 4) * 4 AS h4, count() AS users,
       round(countIf(cat = 'Books & Media') / users, 3) AS books, round(countIf(cat = 'Toys & Baby') / users, 3) AS toys, round(countIf(cat = 'Electronics') / users, 3) AS electronics, round(countIf(cat = 'Fashion') / users, 3) AS fashion,
       round(countIf(cat = 'Home & Kitchen') / users, 3) AS kitchen, round(countIf(cat = 'Computers & Gaming') / users, 3) AS computers
FROM (SELECT e.u AS u, e.t AS t, e.dev AS dev, e.reg AS reg, c.category::String AS cat
      FROM (SELECT user_id::String AS u, min(ts::DateTime64(3)) AS t, argMin(product_id::String, ts::DateTime64(3)) AS p, any(device::String) AS dev, any(region::String) AS reg FROM shop.events
            WHERE event_type::String = 'view' AND user_id::String IN (SELECT user_id::String FROM shop.requests WHERE is_new_user::Bool) GROUP BY u) e
      JOIN shop.catalog c ON c.product_id::String = e.p)
GROUP BY seg, h4 ORDER BY seg, h4;

-- live home returning: recency vs volume (last history session vs top category), products never carted or bought
WITH imp AS (SELECT r.u AS u, f.sh[k] AS sp, 1 / log2(k + 1) AS w, f.ck AS ck, f.pu AS pu
             FROM (SELECT request_id::String AS id, shown::Array(String) AS sh, clicked::String AS ck, purchased::String AS pu, arrayJoin(range(1, 11)) AS k FROM {TEAM}.feedback) f
             JOIN (SELECT request_id::String AS id, user_id::String AS u FROM shop.requests WHERE length(recent_views::Array(JSON)) = 0 AND NOT is_new_user::Bool) r ON r.id = f.id),
     he AS (SELECT e.user_id::String AS u, e.session_id::String AS s, e.ts::DateTime64(3) AS t, e.product_id::String AS p, e.event_type::String AS et, c.category::String AS cat, c.subcategory::String AS sub, c.brand::String AS br
            FROM shop.history_events e JOIN shop.catalog c ON c.product_id::String = e.product_id::String WHERE e.user_id::String IN (SELECT DISTINCT u FROM imp)),
     ls AS (SELECT u, argMax(s, t) AS s FROM he GROUP BY u),
     lsc AS (SELECT DISTINCT he.u AS u, he.cat AS cat FROM he JOIN ls ON ls.u = he.u AND ls.s = he.s),
     lsp AS (SELECT DISTINCT he.u AS u, he.p AS p FROM he JOIN ls ON ls.u = he.u AND ls.s = he.s WHERE he.et = 'view'),
     up AS (SELECT u, p, countIf(et = 'add_to_cart') AS nc, countIf(et = 'purchase') AS nb, countIf(et = 'view') AS nv FROM he GROUP BY u, p),
     tc AS (SELECT u, argMax(cat, n) AS top FROM (SELECT u, cat, count() AS n FROM he WHERE et = 'view' GROUP BY u, cat) GROUP BY u)
SELECT multiIf(up.nb > 0, '0 bought', up.nc > 0, '1 cart', lsp.u != '', '2 viewed in last session', up.nv > 0, '3 viewed earlier', '4 never') AS product,
       multiIf(c.category::String = tc.top AND lsc.u != '', 'top cat, in last session', c.category::String = tc.top, 'top cat, not in last session', lsc.u != '', 'other cat, in last session', 'other cat') AS category,
       count() AS n, round(sum(w)) AS wsum, countIf(ck = sp) AS clicks, countIf(pu = sp) AS buys, round(100 * clicks / wsum, 3) AS wctr, round(100 * buys / wsum, 4) AS wconv
FROM imp JOIN shop.catalog c ON c.product_id::String = imp.sp
LEFT JOIN up ON up.u = imp.u AND up.p = imp.sp LEFT JOIN tc ON tc.u = imp.u LEFT JOIN lsc ON lsc.u = imp.u AND lsc.cat = c.category::String LEFT JOIN lsp ON lsp.u = imp.u AND lsp.p = imp.sp
GROUP BY product, category ORDER BY product, category;

-- live home returning: products never touched, top subcategory and brand seen before
WITH imp AS (SELECT r.u AS u, f.sh[k] AS sp, 1 / log2(k + 1) AS w, f.ck AS ck, f.pu AS pu
             FROM (SELECT request_id::String AS id, shown::Array(String) AS sh, clicked::String AS ck, purchased::String AS pu, arrayJoin(range(1, 11)) AS k FROM {TEAM}.feedback) f
             JOIN (SELECT request_id::String AS id, user_id::String AS u FROM shop.requests WHERE length(recent_views::Array(JSON)) = 0 AND NOT is_new_user::Bool) r ON r.id = f.id),
     he AS (SELECT e.user_id::String AS u, e.product_id::String AS p, e.event_type::String AS et, c.category::String AS cat, c.subcategory::String AS sub, c.brand::String AS br
            FROM shop.history_events e JOIN shop.catalog c ON c.product_id::String = e.product_id::String WHERE e.user_id::String IN (SELECT DISTINCT u FROM imp)),
     up AS (SELECT DISTINCT u, p FROM he),
     sr AS (SELECT u, sub, row_number() OVER (PARTITION BY u, cat ORDER BY n DESC, sub) AS r FROM (SELECT u, cat, sub, count() AS n FROM he WHERE et = 'view' GROUP BY u, cat, sub)),
     bs AS (SELECT DISTINCT u, br FROM he WHERE et = 'view'),
     tc AS (SELECT u, argMax(cat, n) AS top FROM (SELECT u, cat, count() AS n FROM he WHERE et = 'view' GROUP BY u, cat) GROUP BY u)
SELECT c.category::String = tc.top AS top_cat, multiIf(sr.r = 1, '1 top sub in cat', sr.r > 1, '2 other viewed sub', '3 never viewed sub') AS sub, bs.u != '' AS brand_seen,
       count() AS n, round(sum(w)) AS wsum, countIf(ck = sp) AS clicks, countIf(pu = sp) AS buys, round(100 * clicks / wsum, 3) AS wctr, round(100 * buys / wsum, 4) AS wconv
FROM imp JOIN shop.catalog c ON c.product_id::String = imp.sp
LEFT JOIN up ON up.u = imp.u AND up.p = imp.sp LEFT JOIN tc ON tc.u = imp.u LEFT JOIN sr ON sr.u = imp.u AND sr.sub = c.subcategory::String LEFT JOIN bs ON bs.u = imp.u AND bs.br = c.brand::String
WHERE up.u = '' GROUP BY top_cat, sub, brand_seen ORDER BY top_cat, sub, brand_seen;

-- live home: by device x region group, new and returning, clicks and buys
SELECT multiIf(r.dev = 'android' AND r.reg IN ('Andalucía', 'Canarias', 'Murcia'), '1 android-south', r.dev = 'android', '2 android-other', r.dev = 'ios', '3 ios', '4 web') AS seg, r.nu AS new_user,
       count() AS n, countIf(f.ck != '') AS clicks, countIf(f.pu != '') AS buys, round(100 * buys / n, 3) AS conv
FROM (SELECT request_id::String AS id, clicked::String AS ck, purchased::String AS pu FROM {TEAM}.feedback) f
JOIN (SELECT request_id::String AS id, is_new_user::Bool AS nu, context.device::String AS dev, context.region::String AS reg FROM shop.requests WHERE length(recent_views::Array(JSON)) = 0) r ON r.id = f.id
GROUP BY seg, new_user ORDER BY seg, new_user;

-- live home: explore arm by stratum
SELECT x.stratum AS stratum, r.nu AS new_user, count() AS n, countIf(f.ck != '') AS clicks, countIf(f.pu != '') AS buys
FROM (SELECT request_id::String AS id, stratum::String AS stratum FROM {TEAM}.scratch WHERE kind::String = 'explore') x
JOIN (SELECT request_id::String AS id, clicked::String AS ck, purchased::String AS pu FROM {TEAM}.feedback) f ON f.id = x.id
JOIN (SELECT request_id::String AS id, is_new_user::Bool AS nu FROM shop.requests WHERE length(recent_views::Array(JSON)) = 0) r ON r.id = x.id
GROUP BY stratum, new_user ORDER BY stratum, new_user;

-- live home returning: share of requests whose shopper has cart-not-bought products, and the conversion when one was shown
WITH rq AS (SELECT f.id AS id, r.u AS u, f.sh AS sh, f.pu AS pu, f.ck AS ck FROM (SELECT request_id::String AS id, shown::Array(String) AS sh, clicked::String AS ck, purchased::String AS pu FROM {TEAM}.feedback) f
            JOIN (SELECT request_id::String AS id, user_id::String AS u FROM shop.requests WHERE length(recent_views::Array(JSON)) = 0 AND NOT is_new_user::Bool) r ON r.id = f.id),
     cart AS (SELECT u, groupArray(p) AS ps FROM (SELECT user_id::String AS u, product_id::String AS p FROM shop.history_events WHERE user_id::String IN (SELECT DISTINCT u FROM rq)
              GROUP BY u, p HAVING countIf(event_type::String = 'add_to_cart') > 0 AND countIf(event_type::String = 'purchase') = 0) GROUP BY u)
SELECT length(cart.ps) > 0 AS has_cart, arrayExists(p -> has(cart.ps, p), sh) AS cart_shown, count() AS n, countIf(ck != '') AS clicks, countIf(pu != '') AS buys, round(100 * buys / n, 3) AS conv
FROM rq LEFT JOIN cart ON cart.u = rq.u GROUP BY has_cart, cart_shown ORDER BY has_cart, cart_shown;

-- live home: conversion per strategy label, served_by and shopper type
SELECT splitByChar('@', ifNull(s.mv, 'fallback'))[1] AS mv, f.sb AS sb, r.nu AS new_user, count() AS n, countIf(f.ck != '') AS clicks, countIf(f.pu != '') AS buys, round(100 * buys / n, 3) AS conv
FROM (SELECT request_id::String AS id, served_by::String AS sb, clicked::String AS ck, purchased::String AS pu FROM {TEAM}.feedback) f
JOIN (SELECT request_id::String AS id, is_new_user::Bool AS nu FROM shop.requests WHERE length(recent_views::Array(JSON)) = 0) r ON r.id = f.id
LEFT JOIN (SELECT request_id::String AS id, any(model_version::String) AS mv FROM {TEAM}.submissions GROUP BY id) s ON s.id = f.id
GROUP BY mv, sb, new_user ORDER BY mv, sb, new_user;

-- live home returning: cart products shown per strategy
WITH rq AS (SELECT f.id AS id, r.u AS u, f.sh AS sh, f.pu AS pu, f.ck AS ck, s.mv AS mv FROM (SELECT request_id::String AS id, shown::Array(String) AS sh, clicked::String AS ck, purchased::String AS pu FROM {TEAM}.feedback) f
            JOIN (SELECT request_id::String AS id, user_id::String AS u FROM shop.requests WHERE length(recent_views::Array(JSON)) = 0 AND NOT is_new_user::Bool) r ON r.id = f.id
            JOIN (SELECT request_id::String AS id, splitByChar('@', any(model_version::String))[1] AS mv FROM {TEAM}.submissions GROUP BY id) s ON s.id = f.id),
     cart AS (SELECT u, groupArray(p) AS ps FROM (SELECT user_id::String AS u, product_id::String AS p FROM shop.history_events WHERE user_id::String IN (SELECT DISTINCT u FROM rq)
              GROUP BY u, p HAVING countIf(event_type::String = 'add_to_cart') > 0 AND countIf(event_type::String = 'purchase') = 0) GROUP BY u)
SELECT mv, count() AS n, round(avg(arrayCount(p -> has(cart.ps, p), sh)), 2) AS carts_shown, round(avg(arrayCount(p -> has(cart.ps, p), arraySlice(sh, 1, 3))), 2) AS carts_top3, countIf(ck != '') AS clicks, countIf(pu != '') AS buys, round(100 * buys / n, 3) AS conv
FROM rq LEFT JOIN cart ON cart.u = rq.u GROUP BY mv ORDER BY mv;

-- ceiling estimate, returning home: carts first (live rates per weighted impression 0.92 for 2+ carts, 0.23 for one), then 0.07
WITH rq AS (SELECT r.u AS u FROM (SELECT request_id::String AS id FROM {TEAM}.feedback) f JOIN (SELECT request_id::String AS id, user_id::String AS u FROM shop.requests WHERE length(recent_views::Array(JSON)) = 0 AND NOT is_new_user::Bool) r ON r.id = f.id),
     c AS (SELECT u, countIf(nc >= 2) AS n2, countIf(nc = 1) AS n1 FROM (SELECT user_id::String AS u, product_id::String AS p, countIf(event_type::String = 'add_to_cart') AS nc, countIf(event_type::String = 'purchase') AS nb FROM shop.history_events WHERE user_id::String IN (SELECT DISTINCT u FROM rq) GROUP BY u, p) WHERE nb = 0 GROUP BY u),
     x AS (SELECT arrayMap(k -> if(k <= c.n2, 0.92, if(k <= c.n2 + c.n1, 0.23, 0.07)) / log2(k + 1), range(1, 11)) AS r, c.n2 AS n2, c.n1 AS n1 FROM rq LEFT JOIN c ON c.u = rq.u)
SELECT count() AS requests, round(avg(arraySum(r)), 3) AS expected_conv_pct, round(avg(n2 > 0), 3) AS share_cart2, round(avg(n1 + n2 > 0), 3) AS share_cart, quantiles(0.5, 0.9)(n2) AS n2q, quantiles(0.5, 0.9)(n1) AS n1q FROM x;
