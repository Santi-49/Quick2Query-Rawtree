-- One row per product: organic history views and purchases
SELECT product_id::String AS p,
       countIf(event_type::String = 'view') AS views,
       countIf(event_type::String = 'purchase') AS buys
FROM shop.history_events
GROUP BY p
