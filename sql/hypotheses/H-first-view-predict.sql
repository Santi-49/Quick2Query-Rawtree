-- H-first-view-predict: what a brand-new shopper with zero recent views views next, and how concentrated it is by segment.
-- Live: shop.requests (is_new_user, first request on home) joined to shop.events. History: first session of each user in history_events.

-- gap from first home request to first view, fresh users
WITH fr AS (SELECT user_id::String AS u, min(ts::DateTime64(3)) AS t0, argMin(context.page::String, ts::DateTime64(3)) AS page FROM shop.requests WHERE is_new_user::Bool GROUP BY u HAVING page = 'home'),
     j AS (SELECT fr.u AS u, countIf(e.t < fr.t0) AS nb, minIf(dateDiff('millisecond', fr.t0, e.t) / 1000, e.t >= fr.t0 AND e.et = 'view') AS gap, maxIf(dateDiff('millisecond', e.t, fr.t0) / 1000, e.t < fr.t0) AS lastgap
           FROM fr LEFT JOIN (SELECT user_id::String AS u, ts::DateTime64(3) AS t, event_type::String AS et FROM shop.events) e ON e.u = fr.u GROUP BY fr.u)
SELECT nb > 0 AS had_events_before, count() AS users, quantiles(0.1, 0.25, 0.5, 0.75, 0.9)(gap) AS gap_to_first_view_s, countIf(gap < 60) AS within_60s, countIf(gap < 600) AS within_600s
FROM j GROUP BY had_events_before;

-- concentration of first viewed category and product of a first session, by segment group (history first session of each user)
WITH fs AS (SELECT user_id::String AS u, argMin(session_id::String, ts::DateTime64(3)) AS s FROM shop.history_events GROUP BY u),
     fv AS (SELECT e.user_id::String AS u, argMin(e.product_id::String, e.ts::DateTime64(3)) AS p, any(multiIf(e.device::String = 'android' AND e.region::String IN ('Andalucía', 'Canarias', 'Murcia'), '1 android-south', e.device::String = 'android', '2 android-other', e.device::String = 'ios', '3 ios', '4 web')) AS seg
            FROM shop.history_events e WHERE e.event_type::String = 'view' AND (e.user_id::String, e.session_id::String) IN (SELECT u, s FROM fs) GROUP BY u),
     x AS (SELECT fv.seg AS seg, fv.p AS p, c.category::String AS cat FROM fv JOIN shop.catalog c ON c.product_id::String = fv.p),
     cc AS (SELECT seg, cat, count() AS n FROM x GROUP BY seg, cat),
     pc AS (SELECT seg, p, count() AS n FROM x GROUP BY seg, p)
SELECT a.seg AS seg, a.users AS users, a.top_cats AS top_cats, round(a.top1, 3) AS top1_cat_share, round(a.top3, 3) AS top3_cat_share, round(b.top10, 3) AS top10_product_share, round(b.top50, 3) AS top50_product_share
FROM (SELECT seg, sum(n) AS users, arraySlice(arrayMap(t -> concat(t.2, ' ', toString(round(t.1 / users, 3))), arrayReverseSort(groupArray((n, cat)))), 1, 4) AS top_cats,
             arrayReverseSort(groupArray(n))[1] / users AS top1, arraySum(arraySlice(arrayReverseSort(groupArray(n)), 1, 3)) / users AS top3 FROM cc GROUP BY seg) a
JOIN (SELECT seg, arraySum(arraySlice(arrayReverseSort(groupArray(n)), 1, 10)) / sum(n) AS top10, arraySum(arraySlice(arrayReverseSort(groupArray(n)), 1, 50)) / sum(n) AS top50 FROM pc GROUP BY seg) b USING seg
ORDER BY seg;

-- same, live: first view after the first home request of a new shopper
WITH fr AS (SELECT user_id::String AS u, min(ts::DateTime64(3)) AS t0, argMin(context.page::String, ts::DateTime64(3)) AS page,
                   argMin(multiIf(context.device::String = 'android' AND context.region::String IN ('Andalucía', 'Canarias', 'Murcia'), '1 android-south', context.device::String = 'android', '2 android-other', context.device::String = 'ios', '3 ios', '4 web'), ts::DateTime64(3)) AS seg
            FROM shop.requests WHERE is_new_user::Bool GROUP BY u HAVING page = 'home'),
     fv AS (SELECT fr.u AS u, any(fr.seg) AS seg, argMin(e.p, e.t) AS p FROM fr JOIN (SELECT user_id::String AS u, ts::DateTime64(3) AS t, product_id::String AS p FROM shop.events WHERE event_type::String = 'view') e ON e.u = fr.u
            WHERE e.t >= fr.t0 GROUP BY fr.u),
     x AS (SELECT fv.seg AS seg, fv.p AS p, c.category::String AS cat FROM fv JOIN shop.catalog c ON c.product_id::String = fv.p),
     cc AS (SELECT seg, cat, count() AS n FROM x GROUP BY seg, cat),
     pc AS (SELECT seg, p, count() AS n FROM x GROUP BY seg, p)
SELECT a.seg AS seg, a.users AS users, a.top_cats AS top_cats, round(a.top1, 3) AS top1_cat_share, round(a.top3, 3) AS top3_cat_share, round(b.top10, 3) AS top10_product_share, round(b.top50, 3) AS top50_product_share
FROM (SELECT seg, sum(n) AS users, arraySlice(arrayMap(t -> concat(t.2, ' ', toString(round(t.1 / users, 3))), arrayReverseSort(groupArray((n, cat)))), 1, 4) AS top_cats,
             arrayReverseSort(groupArray(n))[1] / users AS top1, arraySum(arraySlice(arrayReverseSort(groupArray(n)), 1, 3)) / users AS top3 FROM cc GROUP BY seg) a
JOIN (SELECT seg, arraySum(arraySlice(arrayReverseSort(groupArray(n)), 1, 10)) / sum(n) AS top10, arraySum(arraySlice(arrayReverseSort(groupArray(n)), 1, 50)) / sum(n) AS top50 FROM pc GROUP BY seg) b USING seg
ORDER BY seg;

-- live: all first views of new shoppers today (first event of the day), concentration by segment
WITH nu AS (SELECT DISTINCT user_id::String AS u FROM shop.requests WHERE is_new_user::Bool),
     fv AS (SELECT user_id::String AS u, argMin(product_id::String, ts::DateTime64(3)) AS p,
                   any(multiIf(device::String = 'android' AND region::String IN ('Andalucía', 'Canarias', 'Murcia'), '1 android-south', device::String = 'android', '2 android-other', device::String = 'ios', '3 ios', '4 web')) AS seg
            FROM shop.events WHERE event_type::String = 'view' AND user_id::String IN (SELECT u FROM nu) GROUP BY u),
     x AS (SELECT fv.seg AS seg, fv.p AS p, c.category::String AS cat FROM fv JOIN shop.catalog c ON c.product_id::String = fv.p),
     cc AS (SELECT seg, cat, count() AS n FROM x GROUP BY seg, cat),
     pc AS (SELECT seg, p, count() AS n FROM x GROUP BY seg, p)
SELECT a.seg AS seg, a.users AS users, a.top_cats AS top_cats, round(a.top1, 3) AS top1_cat_share, round(a.top3, 3) AS top3_cat_share, round(b.top10, 3) AS top10_product_share, round(b.top50, 3) AS top50_product_share
FROM (SELECT seg, sum(n) AS users, arraySlice(arrayMap(t -> concat(t.2, ' ', toString(round(t.1 / users, 3))), arrayReverseSort(groupArray((n, cat)))), 1, 4) AS top_cats,
             arrayReverseSort(groupArray(n))[1] / users AS top1, arraySum(arraySlice(arrayReverseSort(groupArray(n)), 1, 3)) / users AS top3 FROM cc GROUP BY seg) a
JOIN (SELECT seg, arraySum(arraySlice(arrayReverseSort(groupArray(n)), 1, 10)) / sum(n) AS top10, arraySum(arraySlice(arrayReverseSort(groupArray(n)), 1, 50)) / sum(n) AS top50 FROM pc GROUP BY seg) b USING seg
ORDER BY seg;

-- live new shoppers: next-view category after the home request vs categories viewed earlier today
WITH fr AS (SELECT user_id::String AS u, min(ts::DateTime64(3)) AS t0, argMin(context.page::String, ts::DateTime64(3)) AS page FROM shop.requests WHERE is_new_user::Bool GROUP BY u HAVING page = 'home'),
     ev AS (SELECT e.user_id::String AS u, e.ts::DateTime64(3) AS t, e.product_id::String AS p, e.event_type::String AS et, c.category::String AS cat, c.subcategory::String AS sub
            FROM shop.events e JOIN shop.catalog c ON c.product_id::String = e.product_id::String WHERE e.user_id::String IN (SELECT u FROM fr)),
     per AS (SELECT fr.u AS u, argMinIf(ev.cat, ev.t, ev.t >= fr.t0 AND ev.et = 'view') AS next_cat, argMinIf(ev.p, ev.t, ev.t >= fr.t0 AND ev.et = 'view') AS next_p,
                    countIf(ev.t >= fr.t0 AND ev.et = 'view') AS n_after, countIf(ev.t < fr.t0 AND ev.et = 'view') AS n_before,
                    arrayMap(t -> t.2, arrayReverseSort(arrayMap(c -> (countEqual(groupArrayIf(ev.cat, ev.t < fr.t0 AND ev.et = 'view'), c), c), arrayDistinct(groupArrayIf(ev.cat, ev.t < fr.t0 AND ev.et = 'view'))))) AS cats_before,
                    groupArrayIf(ev.p, ev.t < fr.t0 AND ev.et = 'view') AS ps_before, groupArrayIf(ev.cat, ev.t >= fr.t0 AND ev.et = 'purchase') AS buy_cats_after
             FROM fr LEFT JOIN ev ON ev.u = fr.u GROUP BY fr.u)
SELECT n_before > 0 AS had_views_before, count() AS users, countIf(n_after > 0) AS with_next_view,
       round(countIf(n_after > 0 AND next_cat = cats_before[1]) / with_next_view, 3) AS next_cat_is_top_before,
       round(countIf(n_after > 0 AND has(arraySlice(cats_before, 1, 3), next_cat)) / with_next_view, 3) AS next_cat_in_top3_before,
       round(countIf(n_after > 0 AND has(cats_before, next_cat)) / with_next_view, 3) AS next_cat_seen_before,
       round(countIf(n_after > 0 AND has(ps_before, next_p)) / with_next_view, 3) AS next_product_seen_before,
       round(avg(length(cats_before)), 2) AS cats_before_mean,
       countIf(length(buy_cats_after) > 0) AS buyers_after, round(countIf(length(buy_cats_after) > 0 AND has(buy_cats_after, cats_before[1])) / buyers_after, 3) AS buy_in_top_before
FROM per GROUP BY had_views_before;

-- history: next session first-view category vs the user's top category so far (sessions in the last 10 days, profile from before)
WITH s AS (SELECT user_id::String AS u, session_id::String AS sid, min(ts::DateTime64(3)) AS t, argMin(product_id::String, ts::DateTime64(3)) AS p FROM shop.history_events
           WHERE event_type::String = 'view' AND ts::DateTime64(3) >= '2026-11-04 07:00:00' GROUP BY u, sid),
     top AS (SELECT u, groupArray(cat) AS cats FROM (SELECT e.user_id::String AS u, c.category::String AS cat, count() AS n FROM shop.history_events e JOIN shop.catalog c ON c.product_id::String = e.product_id::String
             WHERE e.event_type::String = 'view' AND e.ts::DateTime64(3) < '2026-11-04 07:00:00' GROUP BY u, cat ORDER BY u, n DESC) GROUP BY u)
SELECT count() AS sessions, round(countIf(c.category::String = top.cats[1]) / sessions, 3) AS first_cat_is_top1, round(countIf(has(arraySlice(top.cats, 1, 3), c.category::String)) / sessions, 3) AS first_cat_in_top3
FROM s JOIN shop.catalog c ON c.product_id::String = s.p JOIN top ON top.u = s.u;
