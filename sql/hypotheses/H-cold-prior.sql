-- H-cold-prior: for new shoppers, purchase probability by category depends on device x region.
-- History carousel: rate per request of the shown category (one category per request). Groups: android in Andalucia/Canarias/Murcia, other android, ios, web.

-- group x category purchase pct (buys), all sessions
WITH r AS (SELECT user_id::String AS u, ts::DateTime64(3) AS t, multiIf(context.device::String = 'android' AND context.region::String IN ('Andalucía', 'Canarias', 'Murcia'), '1 android-south', context.device::String = 'android', '2 android-other', context.device::String = 'ios', '3 ios', '4 web') AS seg, context.page::String AS page, (shown::Array(String))[1] AS s1, isNotNull(purchased) AS b,
                   row_number() OVER (PARTITION BY user_id::String ORDER BY ts::DateTime64(3)) AS nth,
                   dateDiff('second', min(ts::DateTime64(3)) OVER (PARTITION BY user_id::String), ts::DateTime64(3)) AS since_first FROM shop.history_sessions),
     base AS (SELECT r.*, c.category::String AS cat FROM r JOIN shop.catalog c ON c.product_id::String = r.s1)
SELECT seg, count() AS requests, countIf(b) AS buys, round(100 * buys / requests, 2) AS conv,
       concat(toString(round(100 * countIf(cat = 'Beauty & Health' AND b) / countIf(cat = 'Beauty & Health'), 2)), ' (', toString(countIf(cat = 'Beauty & Health' AND b)), ')') AS beauty,
       concat(toString(round(100 * countIf(cat = 'Books & Media' AND b) / countIf(cat = 'Books & Media'), 2)), ' (', toString(countIf(cat = 'Books & Media' AND b)), ')') AS books,
       concat(toString(round(100 * countIf(cat = 'Computers & Gaming' AND b) / countIf(cat = 'Computers & Gaming'), 2)), ' (', toString(countIf(cat = 'Computers & Gaming' AND b)), ')') AS computers,
       concat(toString(round(100 * countIf(cat = 'Electronics' AND b) / countIf(cat = 'Electronics'), 2)), ' (', toString(countIf(cat = 'Electronics' AND b)), ')') AS electronics,
       concat(toString(round(100 * countIf(cat = 'Fashion' AND b) / countIf(cat = 'Fashion'), 2)), ' (', toString(countIf(cat = 'Fashion' AND b)), ')') AS fashion,
       concat(toString(round(100 * countIf(cat = 'Home & Garden' AND b) / countIf(cat = 'Home & Garden'), 2)), ' (', toString(countIf(cat = 'Home & Garden' AND b)), ')') AS garden,
       concat(toString(round(100 * countIf(cat = 'Home & Kitchen' AND b) / countIf(cat = 'Home & Kitchen'), 2)), ' (', toString(countIf(cat = 'Home & Kitchen' AND b)), ')') AS kitchen,
       concat(toString(round(100 * countIf(cat = 'Pets' AND b) / countIf(cat = 'Pets'), 2)), ' (', toString(countIf(cat = 'Pets' AND b)), ')') AS pets,
       concat(toString(round(100 * countIf(cat = 'Sports & Outdoors' AND b) / countIf(cat = 'Sports & Outdoors'), 2)), ' (', toString(countIf(cat = 'Sports & Outdoors' AND b)), ')') AS sports,
       concat(toString(round(100 * countIf(cat = 'Toys & Baby' AND b) / countIf(cat = 'Toys & Baby'), 2)), ' (', toString(countIf(cat = 'Toys & Baby' AND b)), ')') AS toys
FROM base WHERE 1 GROUP BY seg ORDER BY seg;

-- group x category purchase pct (buys), first request of each user
WITH r AS (SELECT user_id::String AS u, ts::DateTime64(3) AS t, multiIf(context.device::String = 'android' AND context.region::String IN ('Andalucía', 'Canarias', 'Murcia'), '1 android-south', context.device::String = 'android', '2 android-other', context.device::String = 'ios', '3 ios', '4 web') AS seg, context.page::String AS page, (shown::Array(String))[1] AS s1, isNotNull(purchased) AS b,
                   row_number() OVER (PARTITION BY user_id::String ORDER BY ts::DateTime64(3)) AS nth,
                   dateDiff('second', min(ts::DateTime64(3)) OVER (PARTITION BY user_id::String), ts::DateTime64(3)) AS since_first FROM shop.history_sessions),
     base AS (SELECT r.*, c.category::String AS cat FROM r JOIN shop.catalog c ON c.product_id::String = r.s1)
SELECT seg, count() AS requests, countIf(b) AS buys, round(100 * buys / requests, 2) AS conv,
       concat(toString(round(100 * countIf(cat = 'Beauty & Health' AND b) / countIf(cat = 'Beauty & Health'), 2)), ' (', toString(countIf(cat = 'Beauty & Health' AND b)), ')') AS beauty,
       concat(toString(round(100 * countIf(cat = 'Books & Media' AND b) / countIf(cat = 'Books & Media'), 2)), ' (', toString(countIf(cat = 'Books & Media' AND b)), ')') AS books,
       concat(toString(round(100 * countIf(cat = 'Computers & Gaming' AND b) / countIf(cat = 'Computers & Gaming'), 2)), ' (', toString(countIf(cat = 'Computers & Gaming' AND b)), ')') AS computers,
       concat(toString(round(100 * countIf(cat = 'Electronics' AND b) / countIf(cat = 'Electronics'), 2)), ' (', toString(countIf(cat = 'Electronics' AND b)), ')') AS electronics,
       concat(toString(round(100 * countIf(cat = 'Fashion' AND b) / countIf(cat = 'Fashion'), 2)), ' (', toString(countIf(cat = 'Fashion' AND b)), ')') AS fashion,
       concat(toString(round(100 * countIf(cat = 'Home & Garden' AND b) / countIf(cat = 'Home & Garden'), 2)), ' (', toString(countIf(cat = 'Home & Garden' AND b)), ')') AS garden,
       concat(toString(round(100 * countIf(cat = 'Home & Kitchen' AND b) / countIf(cat = 'Home & Kitchen'), 2)), ' (', toString(countIf(cat = 'Home & Kitchen' AND b)), ')') AS kitchen,
       concat(toString(round(100 * countIf(cat = 'Pets' AND b) / countIf(cat = 'Pets'), 2)), ' (', toString(countIf(cat = 'Pets' AND b)), ')') AS pets,
       concat(toString(round(100 * countIf(cat = 'Sports & Outdoors' AND b) / countIf(cat = 'Sports & Outdoors'), 2)), ' (', toString(countIf(cat = 'Sports & Outdoors' AND b)), ')') AS sports,
       concat(toString(round(100 * countIf(cat = 'Toys & Baby' AND b) / countIf(cat = 'Toys & Baby'), 2)), ' (', toString(countIf(cat = 'Toys & Baby' AND b)), ')') AS toys
FROM base WHERE nth = 1 GROUP BY seg ORDER BY seg;

-- group x category purchase pct (buys), first 3 requests of each user
WITH r AS (SELECT user_id::String AS u, ts::DateTime64(3) AS t, multiIf(context.device::String = 'android' AND context.region::String IN ('Andalucía', 'Canarias', 'Murcia'), '1 android-south', context.device::String = 'android', '2 android-other', context.device::String = 'ios', '3 ios', '4 web') AS seg, context.page::String AS page, (shown::Array(String))[1] AS s1, isNotNull(purchased) AS b,
                   row_number() OVER (PARTITION BY user_id::String ORDER BY ts::DateTime64(3)) AS nth,
                   dateDiff('second', min(ts::DateTime64(3)) OVER (PARTITION BY user_id::String), ts::DateTime64(3)) AS since_first FROM shop.history_sessions),
     base AS (SELECT r.*, c.category::String AS cat FROM r JOIN shop.catalog c ON c.product_id::String = r.s1)
SELECT seg, count() AS requests, countIf(b) AS buys, round(100 * buys / requests, 2) AS conv,
       concat(toString(round(100 * countIf(cat = 'Beauty & Health' AND b) / countIf(cat = 'Beauty & Health'), 2)), ' (', toString(countIf(cat = 'Beauty & Health' AND b)), ')') AS beauty,
       concat(toString(round(100 * countIf(cat = 'Books & Media' AND b) / countIf(cat = 'Books & Media'), 2)), ' (', toString(countIf(cat = 'Books & Media' AND b)), ')') AS books,
       concat(toString(round(100 * countIf(cat = 'Computers & Gaming' AND b) / countIf(cat = 'Computers & Gaming'), 2)), ' (', toString(countIf(cat = 'Computers & Gaming' AND b)), ')') AS computers,
       concat(toString(round(100 * countIf(cat = 'Electronics' AND b) / countIf(cat = 'Electronics'), 2)), ' (', toString(countIf(cat = 'Electronics' AND b)), ')') AS electronics,
       concat(toString(round(100 * countIf(cat = 'Fashion' AND b) / countIf(cat = 'Fashion'), 2)), ' (', toString(countIf(cat = 'Fashion' AND b)), ')') AS fashion,
       concat(toString(round(100 * countIf(cat = 'Home & Garden' AND b) / countIf(cat = 'Home & Garden'), 2)), ' (', toString(countIf(cat = 'Home & Garden' AND b)), ')') AS garden,
       concat(toString(round(100 * countIf(cat = 'Home & Kitchen' AND b) / countIf(cat = 'Home & Kitchen'), 2)), ' (', toString(countIf(cat = 'Home & Kitchen' AND b)), ')') AS kitchen,
       concat(toString(round(100 * countIf(cat = 'Pets' AND b) / countIf(cat = 'Pets'), 2)), ' (', toString(countIf(cat = 'Pets' AND b)), ')') AS pets,
       concat(toString(round(100 * countIf(cat = 'Sports & Outdoors' AND b) / countIf(cat = 'Sports & Outdoors'), 2)), ' (', toString(countIf(cat = 'Sports & Outdoors' AND b)), ')') AS sports,
       concat(toString(round(100 * countIf(cat = 'Toys & Baby' AND b) / countIf(cat = 'Toys & Baby'), 2)), ' (', toString(countIf(cat = 'Toys & Baby' AND b)), ')') AS toys
FROM base WHERE nth <= 3 GROUP BY seg ORDER BY seg;

-- group x category purchase pct (buys), home only, all sessions
WITH r AS (SELECT user_id::String AS u, ts::DateTime64(3) AS t, multiIf(context.device::String = 'android' AND context.region::String IN ('Andalucía', 'Canarias', 'Murcia'), '1 android-south', context.device::String = 'android', '2 android-other', context.device::String = 'ios', '3 ios', '4 web') AS seg, context.page::String AS page, (shown::Array(String))[1] AS s1, isNotNull(purchased) AS b,
                   row_number() OVER (PARTITION BY user_id::String ORDER BY ts::DateTime64(3)) AS nth,
                   dateDiff('second', min(ts::DateTime64(3)) OVER (PARTITION BY user_id::String), ts::DateTime64(3)) AS since_first FROM shop.history_sessions),
     base AS (SELECT r.*, c.category::String AS cat FROM r JOIN shop.catalog c ON c.product_id::String = r.s1)
SELECT seg, count() AS requests, countIf(b) AS buys, round(100 * buys / requests, 2) AS conv,
       concat(toString(round(100 * countIf(cat = 'Beauty & Health' AND b) / countIf(cat = 'Beauty & Health'), 2)), ' (', toString(countIf(cat = 'Beauty & Health' AND b)), ')') AS beauty,
       concat(toString(round(100 * countIf(cat = 'Books & Media' AND b) / countIf(cat = 'Books & Media'), 2)), ' (', toString(countIf(cat = 'Books & Media' AND b)), ')') AS books,
       concat(toString(round(100 * countIf(cat = 'Computers & Gaming' AND b) / countIf(cat = 'Computers & Gaming'), 2)), ' (', toString(countIf(cat = 'Computers & Gaming' AND b)), ')') AS computers,
       concat(toString(round(100 * countIf(cat = 'Electronics' AND b) / countIf(cat = 'Electronics'), 2)), ' (', toString(countIf(cat = 'Electronics' AND b)), ')') AS electronics,
       concat(toString(round(100 * countIf(cat = 'Fashion' AND b) / countIf(cat = 'Fashion'), 2)), ' (', toString(countIf(cat = 'Fashion' AND b)), ')') AS fashion,
       concat(toString(round(100 * countIf(cat = 'Home & Garden' AND b) / countIf(cat = 'Home & Garden'), 2)), ' (', toString(countIf(cat = 'Home & Garden' AND b)), ')') AS garden,
       concat(toString(round(100 * countIf(cat = 'Home & Kitchen' AND b) / countIf(cat = 'Home & Kitchen'), 2)), ' (', toString(countIf(cat = 'Home & Kitchen' AND b)), ')') AS kitchen,
       concat(toString(round(100 * countIf(cat = 'Pets' AND b) / countIf(cat = 'Pets'), 2)), ' (', toString(countIf(cat = 'Pets' AND b)), ')') AS pets,
       concat(toString(round(100 * countIf(cat = 'Sports & Outdoors' AND b) / countIf(cat = 'Sports & Outdoors'), 2)), ' (', toString(countIf(cat = 'Sports & Outdoors' AND b)), ')') AS sports,
       concat(toString(round(100 * countIf(cat = 'Toys & Baby' AND b) / countIf(cat = 'Toys & Baby'), 2)), ' (', toString(countIf(cat = 'Toys & Baby' AND b)), ')') AS toys
FROM base WHERE page = 'home' GROUP BY seg ORDER BY seg;

-- segment x category lift, all pages, all sessions
WITH base AS (SELECT x.dev AS dev, x.reg AS reg, c.category::String AS cat, x.b AS b
              FROM (SELECT context.device::String AS dev, context.region::String AS reg, (shown::Array(String))[1] AS s1, isNotNull(purchased) AS b FROM shop.history_sessions ) x
              JOIN shop.catalog c ON c.product_id::String = x.s1)
SELECT dev, reg, count() AS requests, countIf(b) AS buys, round(100 * buys / requests, 2) AS conv,
       round((countIf(cat = 'Beauty & Health' AND b) / countIf(cat = 'Beauty & Health')) / (SELECT countIf(b) / count() FROM base WHERE cat = 'Beauty & Health'), 2) AS beauty, round((countIf(cat = 'Books & Media' AND b) / countIf(cat = 'Books & Media')) / (SELECT countIf(b) / count() FROM base WHERE cat = 'Books & Media'), 2) AS books, round((countIf(cat = 'Computers & Gaming' AND b) / countIf(cat = 'Computers & Gaming')) / (SELECT countIf(b) / count() FROM base WHERE cat = 'Computers & Gaming'), 2) AS computers, round((countIf(cat = 'Electronics' AND b) / countIf(cat = 'Electronics')) / (SELECT countIf(b) / count() FROM base WHERE cat = 'Electronics'), 2) AS electronics, round((countIf(cat = 'Fashion' AND b) / countIf(cat = 'Fashion')) / (SELECT countIf(b) / count() FROM base WHERE cat = 'Fashion'), 2) AS fashion, round((countIf(cat = 'Home & Garden' AND b) / countIf(cat = 'Home & Garden')) / (SELECT countIf(b) / count() FROM base WHERE cat = 'Home & Garden'), 2) AS garden, round((countIf(cat = 'Home & Kitchen' AND b) / countIf(cat = 'Home & Kitchen')) / (SELECT countIf(b) / count() FROM base WHERE cat = 'Home & Kitchen'), 2) AS kitchen, round((countIf(cat = 'Pets' AND b) / countIf(cat = 'Pets')) / (SELECT countIf(b) / count() FROM base WHERE cat = 'Pets'), 2) AS pets, round((countIf(cat = 'Sports & Outdoors' AND b) / countIf(cat = 'Sports & Outdoors')) / (SELECT countIf(b) / count() FROM base WHERE cat = 'Sports & Outdoors'), 2) AS sports, round((countIf(cat = 'Toys & Baby' AND b) / countIf(cat = 'Toys & Baby')) / (SELECT countIf(b) / count() FROM base WHERE cat = 'Toys & Baby'), 2) AS toys
FROM base GROUP BY dev, reg ORDER BY dev, reg;

-- hour of day, history, home vs other
SELECT intDiv(toHour(ts::DateTime64(3)), 4) * 4 AS hour4, countIf(context.page::String = 'home') AS home_n, round(100 * countIf(context.page::String = 'home' AND isNotNull(purchased)) / home_n, 3) AS home_conv,
       countIf(context.page::String != 'home') AS other_n, round(100 * countIf(context.page::String != 'home' AND isNotNull(purchased)) / other_n, 3) AS other_conv
FROM shop.history_sessions GROUP BY hour4 ORDER BY hour4;

-- day of week, history
SELECT toDayOfWeek(ts::DateTime64(3)) AS dow, countIf(context.page::String = 'home') AS home_n, round(100 * countIf(context.page::String = 'home' AND isNotNull(purchased)) / home_n, 3) AS home_conv,
       countIf(context.page::String != 'home') AS other_n, round(100 * countIf(context.page::String != 'home' AND isNotNull(purchased)) / other_n, 3) AS other_conv
FROM shop.history_sessions GROUP BY dow ORDER BY dow;

-- hour of day x category, history home, top categories
SELECT intDiv(toHour(x.t), 6) * 6 AS hour6, count() AS n, round(100 * countIf(x.b) / n, 3) AS conv,
       round(100 * countIf(c.category::String = 'Books & Media' AND x.b) / countIf(c.category::String = 'Books & Media'), 3) AS books, round(100 * countIf(c.category::String = 'Toys & Baby' AND x.b) / countIf(c.category::String = 'Toys & Baby'), 3) AS toys,
       round(100 * countIf(c.category::String = 'Electronics' AND x.b) / countIf(c.category::String = 'Electronics'), 3) AS electronics, round(100 * countIf(c.category::String = 'Fashion' AND x.b) / countIf(c.category::String = 'Fashion'), 3) AS fashion
FROM (SELECT ts::DateTime64(3) AS t, (shown::Array(String))[1] AS s1, isNotNull(purchased) AS b FROM shop.history_sessions WHERE context.page::String = 'home') x JOIN shop.catalog c ON c.product_id::String = x.s1
GROUP BY hour6 ORDER BY hour6;

-- live new vs returning by page and segment group
SELECT r.context.page::String = 'home' AS home, r.is_new_user::Bool AS new_user, r.context.device::String = 'android' AND r.context.region::String IN ('Andalucía', 'Canarias', 'Murcia') AS android_south,
       count() AS n, countIf(f.clicked::String != '') AS clicks, countIf(f.purchased::String != '') AS buys, round(100 * buys / n, 3) AS conv
FROM {TEAM}.feedback f JOIN shop.requests r ON r.request_id::String = f.request_id::String GROUP BY home, new_user, android_south ORDER BY home, new_user, android_south;

-- live new shoppers, impressions of a category other than the last view (or home), by segment group x category
WITH imp AS (SELECT seg, sh[k] AS sp, 1 / log2(k + 1) AS w, ck, pu, lv
             FROM (SELECT multiIf(r.context.device::String = 'android' AND r.context.region::String IN ('Andalucía', 'Canarias', 'Murcia'), '1 android-south', r.context.device::String = 'android', '2 android-other', r.context.device::String = 'ios', '3 ios', '4 web') AS seg,
                          f.shown::Array(String) AS sh, f.clicked::String AS ck, f.purchased::String AS pu, if(length(r.recent_views) = 0, '', (r.recent_views::Array(JSON))[-1].product_id::String) AS lv, arrayJoin(range(1, 11)) AS k
                   FROM {TEAM}.feedback f JOIN shop.requests r ON r.request_id::String = f.request_id::String WHERE r.is_new_user::Bool))
SELECT seg, c.category::String AS cat, count() AS n, round(sum(w)) AS wsum, countIf(ck = sp) AS clicks, countIf(pu = sp) AS buys, round(100 * clicks / wsum, 3) AS wctr, round(100 * buys / wsum, 3) AS wconv
FROM imp JOIN shop.catalog c ON c.product_id::String = imp.sp LEFT JOIN shop.catalog l ON l.product_id::String = imp.lv
WHERE imp.lv = '' OR l.category::String != c.category::String
GROUP BY seg, cat ORDER BY seg, cat;

-- live new shoppers with recent views: relation of shown product to recent views, slots 1-10 weighted
SELECT multiIf(has(rv, sp), '1 in recent views', c.subcategory::String = l.subcategory::String, '2 same subcategory as last view', c.category::String = l.category::String, '3 same category as last view', '4 other category') AS relation,
       r.seg AS seg, count() AS n, round(sum(w)) AS wsum, countIf(ck = sp) AS clicks, countIf(pu = sp) AS buys, round(100 * clicks / wsum, 3) AS wctr, round(100 * buys / wsum, 3) AS wconv
FROM (SELECT sh[k] AS sp, 1 / log2(k + 1) AS w, ck, pu, rv, rv[-1] AS lv, seg
      FROM (SELECT f.shown::Array(String) AS sh, f.clicked::String AS ck, f.purchased::String AS pu, arrayMap(v -> v.product_id::String, r.recent_views::Array(JSON)) AS rv,
                   r.context.device::String = 'android' AND r.context.region::String IN ('Andalucía', 'Canarias', 'Murcia') AS seg, arrayJoin(range(1, 11)) AS k
            FROM {TEAM}.feedback f JOIN shop.requests r ON r.request_id::String = f.request_id::String WHERE r.is_new_user::Bool AND length(r.recent_views) > 0)) r
JOIN shop.catalog c ON c.product_id::String = r.sp LEFT JOIN shop.catalog l ON l.product_id::String = r.lv
GROUP BY relation, seg ORDER BY relation, seg;
