-- Organic co-views of one hash chunk of the first product: b viewed directly after a in a history session, n >= 3
SELECT a, groupArray(b) AS bs, groupArray(n) AS ns
FROM (
    SELECT a, b, count() AS n
    FROM (
        SELECT product_id::String AS b,
               lagInFrame(product_id::String) OVER (PARTITION BY session_id::String ORDER BY ts::DateTime64(3) ROWS BETWEEN 1 PRECEDING AND CURRENT ROW) AS a
        FROM shop.history_events
        WHERE event_type::String = 'view'
    )
    WHERE a != '' AND a != b AND cityHash64(a) % 16 = {chunk}
    GROUP BY a, b
    HAVING n >= 3
)
GROUP BY a
