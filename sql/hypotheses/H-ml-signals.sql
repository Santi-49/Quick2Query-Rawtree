-- H-ml-signals: the strongest new signals from eda/ml (docs/findings/08-ml-patterns.md), re-run on live feedback.
-- Each impression of {TEAM}.feedback is weighted 1/log2(slot+1), and rates are clicks or purchases per 100 weighted impressions.
-- Shopper history = shop.history_events (all of it, before the live event). Products = shop.catalog + new products from catalog_updates.

-- title: phrase taste. Share of the shopper's history views whose product carries each of the shown product's 2 phrases, summed (known shoppers, products never viewed before)
WITH ['sporty style', 'family-size format', 'luxury feel', 'minimalist design', 'compact and lightweight', 'vintage look', 'travel-ready build', 'waterproof shell',
      'designed for kids', 'handmade finish', 'premium materials', 'wireless connectivity', 'organic ingredients', 'built for professionals', 'bold colours',
      'whisper-quiet operation', 'smart app control', 'recycled materials', 'great value for money', 'extra durability'] AS PH,
cat AS (SELECT product_id::String AS p, arrayFilter(f -> position(description::String, f) > 0, PH) AS ph FROM shop.catalog
        UNION ALL SELECT product_id::String, any(arrayFilter(f -> position(description::String, f) > 0, PH)) FROM shop.catalog_updates
        WHERE change::String = 'new_product' GROUP BY product_id::String),
imp AS (SELECT f.rid AS rid, r.u AS u, k AS slot, f.shown[k] AS p, f.clicked = f.shown[k] AS clk, f.purchased = f.shown[k] AS buy
        FROM (SELECT request_id::String AS rid, any(shown::Array(String)) AS shown, any(clicked::String) AS clicked, any(purchased::String) AS purchased
              FROM {TEAM}.feedback GROUP BY rid) f
        INNER JOIN (SELECT request_id::String AS rid, any(user_id::String) AS u FROM shop.requests WHERE NOT is_new_user::Bool GROUP BY rid) r ON r.rid = f.rid
        ARRAY JOIN arrayEnumerate(f.shown) AS k),
uv AS (SELECT user_id::String AS u, product_id::String AS p, count() AS v FROM shop.history_events WHERE event_type::String = 'view' GROUP BY u, p),
uph AS (SELECT u, phrase, sum(v) / any(tot) AS share FROM (SELECT uv.u AS u, uv.v AS v, c.ph AS ph, sum(uv.v) OVER (PARTITION BY uv.u) AS tot
        FROM uv INNER JOIN cat c ON c.p = uv.p) ARRAY JOIN ph AS phrase GROUP BY u, phrase),
x AS (SELECT i.rid AS rid, i.slot AS slot, i.clk AS clk, i.buy AS buy, sum(uph.share) AS ph_share
      FROM imp i INNER JOIN cat c ON c.p = i.p ARRAY JOIN c.ph AS sp
      LEFT JOIN uph ON uph.u = i.u AND uph.phrase = sp
      LEFT JOIN uv ON uv.u = i.u AND uv.p = i.p
      WHERE uv.v = 0 GROUP BY rid, slot, clk, buy)
SELECT multiIf(ph_share <= 0.22, '1: <=0.22', ph_share <= 0.30, '2: 0.22-0.30', ph_share <= 0.38, '3: 0.30-0.38', '4: >0.38') AS phrase_share,
       count() AS imps, round(sum(1 / log2(slot + 1))) AS w, countIf(clk) AS clicks, countIf(buy) AS buys,
       round(100 * clicks / w, 3) AS click_pw, round(100 * buys / w, 3) AS buy_pw
FROM x GROUP BY phrase_share ORDER BY phrase_share;

-- title: carted in history and not bought. History add_to_cart count of the shopper for the shown product, not bought, against viewed only (returning shoppers, by page)
WITH imp AS (SELECT r.u AS u, r.page AS page, k AS slot, f.shown[k] AS p, f.clicked = f.shown[k] AS clk, f.purchased = f.shown[k] AS buy
        FROM (SELECT request_id::String AS rid, any(shown::Array(String)) AS shown, any(clicked::String) AS clicked, any(purchased::String) AS purchased
              FROM {TEAM}.feedback GROUP BY rid) f
        INNER JOIN (SELECT request_id::String AS rid, any(user_id::String) AS u, any(context.page::String) AS page FROM shop.requests
                    WHERE NOT is_new_user::Bool GROUP BY rid) r ON r.rid = f.rid
        ARRAY JOIN arrayEnumerate(f.shown) AS k),
up AS (SELECT user_id::String AS u, product_id::String AS p, countIf(event_type::String = 'view') AS v, countIf(event_type::String = 'add_to_cart') AS c,
              countIf(event_type::String = 'purchase') AS b FROM shop.history_events GROUP BY u, p)
SELECT i.page AS page, multiIf(up.b > 0, '0 bought', up.c >= 2, '3 carted 2+', up.c = 1, '2 carted once', up.v > 0, '1 viewed only', '1 never') AS history,
       count() AS imps, round(sum(1 / log2(i.slot + 1))) AS w, countIf(i.clk) AS clicks, countIf(i.buy) AS buys,
       round(100 * clicks / w, 3) AS click_pw, round(100 * buys / w, 3) AS buy_pw
FROM imp i LEFT JOIN up ON up.u = i.u AND up.p = i.p
GROUP BY page, history ORDER BY page, history;

-- title: phrases shared with the recent views. Number of (shown phrase, viewed phrase) matches over the request's recent views, shown product not itself in the views, by session relation (all shoppers)
WITH ['sporty style', 'family-size format', 'luxury feel', 'minimalist design', 'compact and lightweight', 'vintage look', 'travel-ready build', 'waterproof shell',
      'designed for kids', 'handmade finish', 'premium materials', 'wireless connectivity', 'organic ingredients', 'built for professionals', 'bold colours',
      'whisper-quiet operation', 'smart app control', 'recycled materials', 'great value for money', 'extra durability'] AS PH,
cat AS (SELECT p, any(ph) AS ph, any(sub) AS sub, any(cat) AS cat FROM (
        SELECT product_id::String AS p, arrayFilter(f -> position(description::String, f) > 0, PH) AS ph, subcategory::String AS sub, category::String AS cat FROM shop.catalog
        UNION ALL SELECT product_id::String, arrayFilter(f -> position(description::String, f) > 0, PH), subcategory::String, category::String FROM shop.catalog_updates
        WHERE change::String = 'new_product') GROUP BY p),
req AS (SELECT f.rid AS rid, f.shown AS shown, f.clicked AS clicked, f.purchased AS purchased, r.views AS views
        FROM (SELECT request_id::String AS rid, any(shown::Array(String)) AS shown, any(clicked::String) AS clicked, any(purchased::String) AS purchased
              FROM {TEAM}.feedback GROUP BY rid) f
        INNER JOIN (SELECT request_id::String AS rid, any(arrayMap(v -> v.product_id::String, recent_views::Array(JSON))) AS views FROM shop.requests
                    GROUP BY rid HAVING length(views) > 0) r ON r.rid = f.rid),
vw AS (SELECT r.rid AS rid, groupArray(c.ph) AS vph, argMax(c.sub, j) AS last_sub, argMax(c.cat, j) AS last_cat
       FROM req r ARRAY JOIN r.views AS v, arrayEnumerate(r.views) AS j INNER JOIN cat c ON c.p = v GROUP BY rid),
imp AS (SELECT r.rid AS rid, k AS slot, r.shown[k] AS p, r.clicked = r.shown[k] AS clk, r.purchased = r.shown[k] AS buy, has(r.views, r.shown[k]) AS in_views
        FROM req r ARRAY JOIN arrayEnumerate(r.shown) AS k)
SELECT multiIf(c.sub = vw.last_sub, '1 same subcat as last', c.cat = vw.last_cat, '2 same cat as last', '3 other') AS relation,
       least(arraySum(arrayMap(x -> length(arrayIntersect(x, c.ph)), vw.vph)), 3) AS phrase_matches,
       count() AS imps, round(sum(1 / log2(i.slot + 1))) AS w, countIf(i.clk) AS clicks, countIf(i.buy) AS buys,
       round(100 * clicks / w, 3) AS click_pw, round(100 * buys / w, 3) AS buy_pw
FROM imp i INNER JOIN cat c ON c.p = i.p INNER JOIN vw ON vw.rid = i.rid
WHERE NOT i.in_views GROUP BY relation, phrase_matches ORDER BY relation, phrase_matches;

-- title: organic co-view. Consecutive-view count in organic history sessions from any recent view to the shown product (shown not in the views), by session relation
WITH cat AS (SELECT product_id::String AS p, subcategory::String AS sub, category::String AS cat FROM shop.catalog),
cov AS (SELECT a, b, count() AS n FROM (SELECT product_id::String AS b, lagInFrame(product_id::String) OVER (PARTITION BY session_id::String ORDER BY ts::DateTime64(3)
        ROWS BETWEEN 1 PRECEDING AND CURRENT ROW) AS a FROM shop.history_events WHERE event_type::String = 'view') WHERE a != '' AND a != b GROUP BY a, b),
req AS (SELECT f.rid AS rid, f.shown AS shown, f.clicked AS clicked, f.purchased AS purchased, r.views AS views
        FROM (SELECT request_id::String AS rid, any(shown::Array(String)) AS shown, any(clicked::String) AS clicked, any(purchased::String) AS purchased
              FROM {TEAM}.feedback GROUP BY rid) f
        INNER JOIN (SELECT request_id::String AS rid, any(arrayMap(v -> v.product_id::String, recent_views::Array(JSON))) AS views FROM shop.requests
                    GROUP BY rid HAVING length(views) > 0) r ON r.rid = f.rid),
pairs AS (SELECT r.rid AS rid, k AS slot, r.shown[k] AS p, r.clicked = r.shown[k] AS clk, r.purchased = r.shown[k] AS buy, r.views[-1] AS last, v
          FROM req r ARRAY JOIN arrayEnumerate(r.shown) AS k ARRAY JOIN r.views AS v WHERE NOT has(r.views, r.shown[k])),
x AS (SELECT rid, slot, any(p) AS p, any(clk) AS clk, any(buy) AS buy, any(last) AS last, sum(cov.n) AS co
      FROM pairs LEFT JOIN cov ON cov.a = pairs.v AND cov.b = pairs.p GROUP BY rid, slot)
SELECT multiIf(c.sub = l.sub, '1 same subcat as last', c.cat = l.cat, '2 same cat as last', '3 other') AS relation,
       multiIf(co = 0, '0', co <= 4, '1-4', co <= 20, '5-20', '21+') AS coview,
       count() AS imps, round(sum(1 / log2(x.slot + 1))) AS w, countIf(x.clk) AS clicks, countIf(x.buy) AS buys,
       round(100 * clicks / w, 3) AS click_pw, round(100 * buys / w, 3) AS buy_pw
FROM x INNER JOIN cat c ON c.p = x.p INNER JOIN cat l ON l.p = x.last
GROUP BY relation, coview ORDER BY relation, coview;
