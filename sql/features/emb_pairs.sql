-- Product co-occurrence for embeddings: products touched (view, cart, purchase) by one shopper on one day, history plus
-- today's live events before {until}; one hash chunk of the first product, ordered pairs a != b, n >= 2
SELECT a, groupArray(b) AS bs, groupArray(n) AS ns
FROM (
    SELECT a, b, count() AS n
    FROM (
        SELECT ps, arrayJoin(arrayFilter(x -> cityHash64(x) % 16 = {chunk}, ps)) AS a
        FROM (
            SELECT groupUniqArray(p) AS ps
            FROM (
                SELECT user_id::String AS u, product_id::String AS p, ts::DateTime64(3) AS t FROM shop.history_events
                WHERE ts::DateTime64(3) >= (SELECT max(ts::DateTime64(3)) FROM shop.history_events) - INTERVAL 30 DAY
                UNION ALL
                SELECT user_id::String AS u, product_id::String AS p, ts::DateTime64(3) AS t FROM shop.events
                WHERE ts::DateTime64(3) < toDateTime64('{until}', 3)
            )
            GROUP BY u, toDate(t)
            HAVING length(ps) BETWEEN 2 AND 50
        )
    )
    ARRAY JOIN ps AS b
    WHERE a != b
    GROUP BY a, b
    HAVING n >= 2
)
GROUP BY a
