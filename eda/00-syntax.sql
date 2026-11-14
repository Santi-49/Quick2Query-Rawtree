-- array cast shown
SELECT arrayJoin(shown::Array(String)) AS p, count() AS n FROM shop.history_sessions GROUP BY p ORDER BY n DESC LIMIT 3;
-- recent views type
SELECT toTypeName(recent_views) AS t, dynamicType(recent_views) AS dt, dynamicType(shown) AS ds, dynamicType(propensity) AS dp, dynamicType(ts) AS dts, dynamicType(clicked) AS dc, count() AS n FROM shop.history_sessions GROUP BY ALL;
-- recent views access a
SELECT recent_views::Array(JSON) AS rv, rv[-1].product_id::String AS last_p FROM shop.history_sessions WHERE length(recent_views) > 1 LIMIT 2;
-- recent views access b
SELECT arrayMap(x -> x.product_id::String, recent_views::Array(JSON)) AS rv FROM shop.history_sessions WHERE length(recent_views) > 1 LIMIT 2;
-- sorting keys
SELECT database, name, engine, sorting_key, total_rows, formatReadableSize(total_bytes) AS size FROM system.tables WHERE database IN ('shop', '{TEAM}');
-- requests types
SELECT dynamicType(ts) AS dts, dynamicType(recent_views) AS drv, dynamicType(is_new_user) AS dn, count() AS n FROM shop.requests GROUP BY ALL
