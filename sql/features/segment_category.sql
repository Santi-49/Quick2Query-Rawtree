-- Old carousel requests and requests with a purchase per device, region and the category shown
SELECT s.device AS device, s.region AS region, c.category AS category,
       count() AS requests, countIf(s.bought) AS buys
FROM (
    SELECT `context.device`::String AS device, `context.region`::String AS region,
           (shown::Array(String))[1] AS first, ifNull(purchased::String, '') != '' AS bought
    FROM shop.history_sessions
) AS s
INNER JOIN (SELECT product_id::String AS p, category::String AS category FROM shop.catalog) AS c ON s.first = c.p
GROUP BY device, region, category
