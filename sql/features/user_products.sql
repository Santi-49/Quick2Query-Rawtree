-- Per user of one hash chunk: products touched, with history view and purchase counts
SELECT u, groupArray(p) AS prods, groupArray(v) AS views, groupArray(b) AS buys
FROM (
    SELECT user_id::String AS u, product_id::String AS p,
           countIf(event_type::String = 'view') AS v,
           countIf(event_type::String = 'purchase') AS b
    FROM shop.history_events
    WHERE cityHash64(user_id::String) % 16 = {chunk}
    GROUP BY u, p
)
GROUP BY u
