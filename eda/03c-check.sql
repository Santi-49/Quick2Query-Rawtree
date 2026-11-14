-- sample rows
SELECT * FROM shop.history_sessions WHERE length(recent_views) = 3 LIMIT 2;

-- number of distinct categories among the 10 shown, by page
SELECT context.page::String AS page, ncat, count() AS n FROM
 (SELECT request_id::String AS rid, any(context.page::String) AS `context.page`, uniqExact(c.category::String) AS ncat
  FROM (SELECT request_id, context.page, arrayJoin(shown::Array(String)) AS sp FROM shop.history_sessions WHERE ts::DateTime64(3) >= '2026-11-12') x
  JOIN shop.catalog c ON c.product_id::String = x.sp GROUP BY rid)
GROUP BY page, ncat ORDER BY page, ncat;

-- share of shown products in the category of the last view, by page
SELECT page, count() AS n, round(avg(c.category::String = l.category::String), 4) AS same_cat, round(avg(c.subcategory::String = l.subcategory::String), 4) AS same_sub
FROM (SELECT context.page::String AS page, arrayJoin(shown::Array(String)) AS sp, (recent_views::Array(JSON))[-1].product_id::String AS lv FROM shop.history_sessions WHERE ts::DateTime64(3) >= '2026-11-12' AND length(recent_views) > 0) x
JOIN shop.catalog c ON c.product_id::String = x.sp
JOIN shop.catalog l ON l.product_id::String = x.lv
GROUP BY page
