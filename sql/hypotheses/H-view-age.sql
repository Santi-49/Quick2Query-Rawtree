-- H-view-age: does the age of the last recent view (request ts - its ts) or the time span of the views change how much the session predicts?
-- Impressions slot-weighted, w = 1/log2(slot+1); ctr_w, conv_w per 100 weighted impressions. Live pools every strategy (the cell, not the list, is compared within an age bucket).
-- Run: uv run scripts/q.py sql/hypotheses/H-view-age.sql [title filter]

-- 1 live: relation to the last view by age of the last view
WITH
prod AS (SELECT pid, any(cat) AS cat, any(sub) AS sub FROM (SELECT product_id::String AS pid, category::String AS cat, subcategory::String AS sub FROM shop.catalog UNION ALL SELECT product_id::String, category::String, subcategory::String FROM shop.catalog_updates WHERE change::String = 'new_product') GROUP BY pid),
fb AS (SELECT request_id::String AS rid, shown::Array(String) AS sh, clicked::String AS ck, purchased::String AS pu FROM {TEAM}.feedback WHERE length(shown::Array(String)) = 10),
rq AS (SELECT request_id::String AS rid, (recent_views::Array(JSON))[-1].product_id::String AS lv,
              dateDiff('millisecond', (recent_views::Array(JSON))[-1].ts::DateTime64(3), ts::DateTime64(3)) / 1000 AS age
       FROM shop.requests WHERE request_id::String IN (SELECT rid FROM fb) AND length(recent_views::Array(JSON)) > 0),
imp AS (SELECT rq.lv AS lv, rq.age AS age, fb.sh[k] AS sp, 1 / log2(k + 1) AS w, fb.ck = fb.sh[k] AS c, fb.pu = fb.sh[k] AS p FROM fb JOIN rq ON rq.rid = fb.rid ARRAY JOIN range(1, 11) AS k)
SELECT multiIf(age < 30, '1 <30s', age < 120, '2 30s-2min', age < 600, '3 2-10min', '4 >10min') AS age_bucket,
       multiIf(sp = lv, '1 last view', a.sub = b.sub, '2 same subcat', a.cat = b.cat, '3 same cat', '4 other') AS relation,
       count() AS imps, round(sum(w)) AS w_imps, sum(c) AS clicks, sum(p) AS buys, round(100 * clicks / w_imps, 3) AS ctr_w, round(100 * buys / w_imps, 3) AS conv_w,
       round(ctr_w / (maxIf(clicks, relation = '4 other') OVER (PARTITION BY age_bucket) / maxIf(w_imps, relation = '4 other') OVER (PARTITION BY age_bucket) * 100), 2) AS click_x
FROM imp JOIN prod a ON a.pid = imp.sp JOIN prod b ON b.pid = imp.lv
GROUP BY age_bucket, relation ORDER BY age_bucket, relation;

-- 2 history: relation to the last view by age of the last view (product and category pages)
WITH
prod AS (SELECT product_id::String AS pid, any(category::String) AS cat, any(subcategory::String) AS sub FROM shop.catalog GROUP BY pid),
s AS (SELECT shown::Array(String) AS sh, (recent_views::Array(JSON))[-1].product_id::String AS lv,
             dateDiff('millisecond', (recent_views::Array(JSON))[-1].ts::DateTime64(3), ts::DateTime64(3)) / 1000 AS age,
             ifNull(clicked::Nullable(String), '') AS ck, ifNull(purchased::Nullable(String), '') AS pu
      FROM shop.history_sessions WHERE context.page::String IN ('product', 'category') AND length(recent_views::Array(JSON)) > 0),
imp AS (SELECT lv, age, sh[k] AS sp, 1 / log2(k + 1) AS w, ck = sh[k] AS c, pu = sh[k] AS p FROM s ARRAY JOIN range(1, 11) AS k)
SELECT multiIf(age < 30, '1 <30s', age < 120, '2 30s-2min', age < 600, '3 2-10min', '4 >10min') AS age_bucket,
       multiIf(sp = lv, '1 last view', a.sub = b.sub, '2 same subcat', '3 same cat') AS relation,
       count() AS imps, round(sum(w)) AS w_imps, sum(c) AS clicks, sum(p) AS buys, round(100 * clicks / w_imps, 3) AS ctr_w, round(100 * buys / w_imps, 3) AS conv_w
FROM imp JOIN prod a ON a.pid = imp.sp JOIN prod b ON b.pid = imp.lv
GROUP BY age_bucket, relation ORDER BY age_bucket, relation;

-- 3 live: relation to the last view by time span of the recent views (last ts - first ts), requests with 2+ views
WITH
prod AS (SELECT pid, any(cat) AS cat, any(sub) AS sub FROM (SELECT product_id::String AS pid, category::String AS cat, subcategory::String AS sub FROM shop.catalog UNION ALL SELECT product_id::String, category::String, subcategory::String FROM shop.catalog_updates WHERE change::String = 'new_product') GROUP BY pid),
fb AS (SELECT request_id::String AS rid, shown::Array(String) AS sh, clicked::String AS ck, purchased::String AS pu FROM {TEAM}.feedback WHERE length(shown::Array(String)) = 10),
rq AS (SELECT request_id::String AS rid, (recent_views::Array(JSON))[-1].product_id::String AS lv,
              dateDiff('millisecond', (recent_views::Array(JSON))[1].ts::DateTime64(3), (recent_views::Array(JSON))[-1].ts::DateTime64(3)) / 1000 AS span
       FROM shop.requests WHERE request_id::String IN (SELECT rid FROM fb) AND length(recent_views::Array(JSON)) > 1),
imp AS (SELECT rq.lv AS lv, rq.span AS span, fb.sh[k] AS sp, 1 / log2(k + 1) AS w, fb.ck = fb.sh[k] AS c, fb.pu = fb.sh[k] AS p FROM fb JOIN rq ON rq.rid = fb.rid ARRAY JOIN range(1, 11) AS k)
SELECT multiIf(span < 60, '1 <1min', span < 300, '2 1-5min', '3 >5min') AS span_bucket,
       multiIf(sp = lv, '1 last view', a.sub = b.sub, '2 same subcat', a.cat = b.cat, '3 same cat', '4 other') AS relation,
       count() AS imps, round(sum(w)) AS w_imps, sum(c) AS clicks, sum(p) AS buys, round(100 * clicks / w_imps, 3) AS ctr_w, round(100 * buys / w_imps, 3) AS conv_w
FROM imp JOIN prod a ON a.pid = imp.sp JOIN prod b ON b.pid = imp.lv
GROUP BY span_bucket, relation ORDER BY span_bucket, relation;

-- 4 share of requests by age of the last view and by span, live and history
SELECT 'live' AS src, count() AS requests, round(100 * countIf(a < 30) / requests, 1) AS pct_lt30s, round(100 * countIf(a >= 30 AND a < 120) / requests, 1) AS pct_30s_2m,
       round(100 * countIf(a >= 120 AND a < 600) / requests, 1) AS pct_2_10m, round(100 * countIf(a >= 600) / requests, 1) AS pct_gt10m, round(quantile(0.5)(a)) AS median_age_s, round(quantile(0.5)(sp)) AS median_span_s
FROM (SELECT dateDiff('millisecond', (recent_views::Array(JSON))[-1].ts::DateTime64(3), ts::DateTime64(3)) / 1000 AS a,
             dateDiff('millisecond', (recent_views::Array(JSON))[1].ts::DateTime64(3), (recent_views::Array(JSON))[-1].ts::DateTime64(3)) / 1000 AS sp
      FROM shop.requests WHERE length(recent_views::Array(JSON)) > 0 AND ts::DateTime64(3) > now() - INTERVAL 3 HOUR)
UNION ALL
SELECT 'history', count(), round(100 * countIf(a < 30) / count(), 1), round(100 * countIf(a >= 30 AND a < 120) / count(), 1), round(100 * countIf(a >= 120 AND a < 600) / count(), 1),
       round(100 * countIf(a >= 600) / count(), 1), round(quantile(0.5)(a)), round(quantile(0.5)(sp))
FROM (SELECT dateDiff('millisecond', (recent_views::Array(JSON))[-1].ts::DateTime64(3), ts::DateTime64(3)) / 1000 AS a,
             dateDiff('millisecond', (recent_views::Array(JSON))[1].ts::DateTime64(3), (recent_views::Array(JSON))[-1].ts::DateTime64(3)) / 1000 AS sp
      FROM shop.history_sessions WHERE length(recent_views::Array(JSON)) > 0);
