-- Carousel history: how the shown product relates to the last viewed product.
-- Price and slot-by-category versions that need the catalogue join are in 03d-carousel-more.sql (recent_views holds only product_id and ts).

-- click and buy rate by relation of the shown product to the last viewed product (product and category pages)
SELECT multiIf(sp = lv, '1 same product', c.subcategory::String = l.subcategory::String AND c.brand::String = l.brand::String, '2 same subcat+brand', c.subcategory::String = l.subcategory::String, '3 same subcategory',
               c.brand::String = l.brand::String, '4 same brand', c.category::String = l.category::String, '5 same category', '6 other category') AS relation,
       count() AS shown_n, round(100 * countIf(ck = sp) / shown_n, 3) AS ctr, round(100 * countIf(pu = sp) / shown_n, 3) AS conv, round(100 * countIf(pu = sp) / countIf(ck = sp), 1) AS buy_given_click, round(avg(k), 2) AS avg_slot
FROM (SELECT sh[k] AS sp, k, ck, pu, lv FROM (SELECT shown::Array(String) AS sh, ifNull(clicked::String, '') AS ck, ifNull(purchased::String, '') AS pu, (recent_views::Array(JSON))[-1].product_id::String AS lv, arrayJoin(range(1, 11)) AS k
      FROM shop.history_sessions WHERE context.page::String != 'home')) x
JOIN shop.catalog c ON c.product_id::String = x.sp
JOIN shop.catalog l ON l.product_id::String = x.lv
GROUP BY relation ORDER BY relation;

-- same, slot 1 only (removes the slot confound)
SELECT multiIf(sp = lv, '1 same product', c.subcategory::String = l.subcategory::String, '3 same subcategory', c.brand::String = l.brand::String, '4 same brand', c.category::String = l.category::String, '5 same category', '6 other category') AS relation,
       count() AS shown_n, round(100 * countIf(ck = sp) / shown_n, 3) AS ctr, round(100 * countIf(pu = sp) / shown_n, 3) AS conv, round(100 * countIf(pu = sp) / countIf(ck = sp), 1) AS buy_given_click
FROM (SELECT (shown::Array(String))[1] AS sp, ifNull(clicked::String, '') AS ck, ifNull(purchased::String, '') AS pu, (recent_views::Array(JSON))[-1].product_id::String AS lv
      FROM shop.history_sessions WHERE context.page::String != 'home') x
JOIN shop.catalog c ON c.product_id::String = x.sp
JOIN shop.catalog l ON l.product_id::String = x.lv
GROUP BY relation ORDER BY relation;

-- home page: click and purchase rate per slot
SELECT k AS slot, count() AS shown_n, round(100 * countIf(ck = sh[k]) / shown_n, 3) AS ctr, round(100 * countIf(pu = sh[k]) / shown_n, 3) AS conv
FROM (SELECT shown::Array(String) AS sh, ifNull(clicked::String, '') AS ck, ifNull(purchased::String, '') AS pu, arrayJoin(range(1, 11)) AS k FROM shop.history_sessions WHERE context.page::String = 'home')
GROUP BY k ORDER BY k
