-- H-drift: do per-product buy propensities move over time? Counts per product x time unit x user half.
-- The user half (cityHash64(user_id) % 2) gives a within-period noise baseline that includes shopper clustering.
-- Read by eda/drift/live.py and eda/drift/history.py. Run alone: uv run scripts/q.py sql/hypotheses/H-drift.sql [title filter]

-- 1 live: views, carts, purchases per product x UTC hour x user half, today 09:00-21:00
SELECT product_id::String AS p, toHour(ts::DateTime64(3, 'UTC')) AS hr, cityHash64(user_id::String) % 2 AS h,
       countIf(event_type::String = 'view') AS v, countIf(event_type::String = 'add_to_cart') AS c, countIf(event_type::String = 'purchase') AS b
FROM shop.events
WHERE ts::DateTime64(3) >= '2026-11-14 09:00:00' AND ts::DateTime64(3) < '2026-11-14 21:00:00'
GROUP BY p, hr, h;

-- 2 history: views, purchases per product x day x user half, full days 16 Sep - 13 Nov
SELECT product_id::String AS p, toString(toDate(ts::DateTime64(3, 'UTC'))) AS d, cityHash64(user_id::String) % 2 AS h,
       countIf(event_type::String = 'view') AS v, countIf(event_type::String = 'purchase') AS b
FROM shop.history_events
WHERE ts::DateTime64(3) >= '2026-09-16 00:00:00' AND ts::DateTime64(3) < '2026-11-14 00:00:00'
GROUP BY p, d, h;

-- 3 natural experiment: live conversion of ranker2 (shale, shale-n) and rules5 (garnet, garnet-n) before, during and after the model freeze 19:47-20:57 UTC
SELECT multiIf(t < '2026-11-14 17:47:00', '0 before 17:47', t < '2026-11-14 19:47:00', '1 17:47-19:47', t < '2026-11-14 20:57:00', '2 frozen 19:47-20:57', '3 after 20:57') AS period,
       mv, count() AS n, countIf(pu != '') AS buys, round(100 * buys / n, 3) AS conv, round(100 * sqrt(buys / n * (1 - buys / n) / n), 3) AS se
FROM (SELECT f.t AS t, f.pu AS pu, s.mv AS mv
      FROM (SELECT request_id::String AS rid, any(ts::DateTime64(3)) AS t, any(purchased::String) AS pu, any(served_by::String) AS sb FROM {TEAM}.feedback GROUP BY rid) f
      INNER JOIN (SELECT request_id::String AS rid, any(model_version::String) AS mv FROM {TEAM}.submissions GROUP BY rid) s ON s.rid = f.rid
      WHERE f.sb = 'team' AND f.t >= '2026-11-14 15:47:00' AND s.mv IN ('shale', 'shale-n', 'garnet', 'garnet-n'))
GROUP BY period, mv ORDER BY mv, period;
