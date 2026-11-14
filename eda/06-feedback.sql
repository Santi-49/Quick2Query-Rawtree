-- Our feedback (team_01.feedback). Until the router exists every answer is the best-seller list, ours or the fallback's.

-- outcome by who served
SELECT served_by::String AS served_by, fallback_reason::String AS reason, count() AS n, round(100 * countIf(clicked::String != '') / n, 2) AS ctr, round(100 * countIf(purchased::String != '') / n, 2) AS conv,
       round(sum(revenue_eur::Float64) / n, 3) AS eur_per_req, uniqExact(shown::Array(String)) AS distinct_lists
FROM {TEAM}.feedback WHERE request_id::String != '__init__' GROUP BY served_by, reason ORDER BY n DESC;

-- latency of our own answers, per 10 minutes (last 2 hours)
SELECT toStartOfTenMinutes(ts::DateTime64(3)) AS t, count() AS n, countIf(served_by::String = 'team') AS ours, round(quantileIf(0.5)(latency_ms::Float64, served_by::String = 'team')) AS p50,
       round(quantileIf(0.95)(latency_ms::Float64, served_by::String = 'team')) AS p95, round(quantileIf(0.99)(latency_ms::Float64, served_by::String = 'team')) AS p99, round(maxIf(latency_ms::Float64, served_by::String = 'team')) AS mx,
       countIf(fallback_reason::String NOT IN ('', 'missing')) AS other_fallbacks
FROM {TEAM}.feedback WHERE ts::DateTime64(3) > now() - INTERVAL 2 HOUR GROUP BY t ORDER BY t;

-- feedback delay: how long after the request does feedback exist (newest request with feedback vs newest request)
SELECT (SELECT max(ts::DateTime64(3)) FROM shop.requests) AS newest_request, (SELECT max(ts::DateTime64(3)) FROM {TEAM}.feedback) AS newest_feedback, (SELECT count() FROM shop.requests) AS requests, (SELECT count() FROM {TEAM}.feedback) - 1 AS feedback_rows;

-- by page and shopper type
SELECT r.context.page::String AS page, r.is_new_user::Bool AS new_user, count() AS n, round(100 * countIf(f.clicked::String != '') / n, 2) AS ctr, round(100 * countIf(f.purchased::String != '') / n, 2) AS conv
FROM {TEAM}.feedback f JOIN shop.requests r ON r.request_id::String = f.request_id::String GROUP BY page, new_user ORDER BY page, new_user;

-- by slot (the list is nearly fixed, so slot and product are confounded)
SELECT k AS slot, any(sh[k]) AS product, count() AS n, round(100 * countIf(ck = sh[k]) / n, 3) AS ctr, round(100 * countIf(pu = sh[k]) / n, 3) AS conv
FROM (SELECT shown::Array(String) AS sh, clicked::String AS ck, purchased::String AS pu, arrayJoin(range(1, 11)) AS k FROM {TEAM}.feedback WHERE request_id::String != '__init__') GROUP BY k ORDER BY k;

-- cross-category: shown product's category vs category of the last viewed product (never observable in the old log)
SELECT multiIf(lv = '', '0 home, no views', sp = lv, '1 same product', c.subcategory::String = l.subcategory::String, '2 same subcategory', c.category::String = l.category::String, '3 same category', '4 other category') AS relation,
       count() AS shown_n, round(100 * countIf(ck = sp) / shown_n, 3) AS ctr, round(100 * countIf(pu = sp) / shown_n, 3) AS conv, round(avg(k), 1) AS avg_slot
FROM (SELECT sh[k] AS sp, k, ck, pu, lv
      FROM (SELECT f.shown::Array(String) AS sh, f.clicked::String AS ck, f.purchased::String AS pu, if(length(r.recent_views) = 0, '', (r.recent_views::Array(JSON))[-1].product_id::String) AS lv, arrayJoin(range(1, 11)) AS k
            FROM {TEAM}.feedback f JOIN shop.requests r ON r.request_id::String = f.request_id::String)) x
JOIN shop.catalog c ON c.product_id::String = x.sp
LEFT JOIN shop.catalog l ON l.product_id::String = x.lv
GROUP BY relation ORDER BY relation;

-- same, slots 1-3 only
SELECT multiIf(lv = '', '0 home, no views', sp = lv, '1 same product', c.subcategory::String = l.subcategory::String, '2 same subcategory', c.category::String = l.category::String, '3 same category', '4 other category') AS relation,
       count() AS shown_n, round(100 * countIf(ck = sp) / shown_n, 3) AS ctr, round(100 * countIf(pu = sp) / shown_n, 3) AS conv
FROM (SELECT sh[k] AS sp, k, ck, pu, lv
      FROM (SELECT f.shown::Array(String) AS sh, f.clicked::String AS ck, f.purchased::String AS pu, if(length(r.recent_views) = 0, '', (r.recent_views::Array(JSON))[-1].product_id::String) AS lv, arrayJoin([1, 2, 3]) AS k
            FROM {TEAM}.feedback f JOIN shop.requests r ON r.request_id::String = f.request_id::String)) x
JOIN shop.catalog c ON c.product_id::String = x.sp
LEFT JOIN shop.catalog l ON l.product_id::String = x.lv
GROUP BY relation ORDER BY relation;

-- live rebuy: shown product bought before by the same user (history), any slot
SELECT multiIf(b.n > 0, '1 bought before', v.n > 0, '2 viewed before, never bought', '3 never seen') AS state, count() AS shown_n, round(100 * countIf(ck = sp) / shown_n, 3) AS ctr, round(100 * countIf(pu = sp) / shown_n, 3) AS conv
FROM (SELECT u, sh[k] AS sp, ck, pu
      FROM (SELECT r.user_id::String AS u, f.shown::Array(String) AS sh, f.clicked::String AS ck, f.purchased::String AS pu, arrayJoin(range(1, 11)) AS k
            FROM {TEAM}.feedback f JOIN shop.requests r ON r.request_id::String = f.request_id::String WHERE NOT r.is_new_user::Bool)) x
LEFT JOIN (SELECT user_id::String AS u, product_id::String AS sp, count() AS n FROM shop.history_events WHERE event_type::String = 'purchase' GROUP BY u, sp) b USING (u, sp)
LEFT JOIN (SELECT user_id::String AS u, product_id::String AS sp, count() AS n FROM shop.history_events WHERE event_type::String = 'view' AND product_id::String IN (SELECT arrayJoin(shown::Array(String)) FROM {TEAM}.feedback) GROUP BY u, sp) v USING (u, sp)
GROUP BY state ORDER BY state;

-- android in the south, live
SELECT r.context.device::String = 'android' AND r.context.region::String IN ('Andalucía', 'Canarias', 'Murcia') AS android_south, r.is_new_user::Bool AS new_user, count() AS n, round(100 * countIf(f.clicked::String != '') / n, 2) AS ctr,
       round(100 * countIf(f.purchased::String != '') / n, 2) AS conv
FROM {TEAM}.feedback f JOIN shop.requests r ON r.request_id::String = f.request_id::String GROUP BY android_south, new_user ORDER BY android_south, new_user
