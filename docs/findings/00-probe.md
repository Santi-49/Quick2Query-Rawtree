# RawTree probe · 2026-11-14 13:07:24 · team_01

## sample catalog

`0.60s`

```sql
SELECT * FROM shop.catalog LIMIT 2
```

```json
[
 {
  "brand": "Vedo",
  "category": "Sports & Outdoors",
  "created_at": "2026-01-21 07:00:00.000000000",
  "description": "Vedo Yoga Mats with organic ingredients and extra durability.",
  "is_active": true,
  "price_eur": 14.99,
  "product_id": "p_001897",
  "subcategory": "Yoga Mats"
 },
 {
  "brand": "Zore",
  "category": "Fashion",
  "created_at": "2025-11-06 07:00:00.000000000",
  "description": "From Zore (Jackets): wireless connectivity, a travel-ready build.",
  "is_active": true,
  "price_eur": 4.99,
  "product_id": "p_00196b",
  "subcategory": "Jackets"
 }
]
```

## sample history_sessions

`0.25s`

```sql
SELECT * FROM shop.history_sessions LIMIT 1
```

```json
[
 {
  "clicked": null,
  "context.device": "web",
  "context.page": "product",
  "context.region": "Catalunya",
  "propensity": [
   0.218886,
   0.002833,
   0.11516,
   0.321647,
   0.02928,
   0.01429,
   0.027197,
   0.034907,
   0.017993,
   7.4e-05
  ],
  "purchased": null,
  "recent_views": [
   {
    "product_id": "p_159190",
    "ts": "2026-09-15 06:56:55.421000000"
   },
   {
    "product_id": "p_159190",
    "ts": "2026-09-15 06:57:20.736000000"
   },
   {
    "product_id": "p_41511c",
    "ts": "2026-09-15 06:59:13.215000000"
   }
  ],
  "request_id": "r_50309edc92778291",
  "revenue_eur": 0,
  "shown": [
   "p_8ca8ed",
   "p_8ac75a",
   "p_e2c959",
   "p_2c88d5",
   "p_8fbfd1",
   "p_7a1c91",
   "p_95d5df",
   "p_b8227f",
   "p_4077a5",
   "p_b45993"
  ],
  "ts": "2026-09-15 07:00:01.456000000",
  "user_id": "u_20cbc5d5"
 }
]
```

## sample history_events

`0.22s`

```sql
SELECT * FROM shop.history_events LIMIT 2
```

```json
[
 {
  "device": "android",
  "event_type": "view",
  "price_eur": 9.99,
  "product_id": "p_d06b48",
  "region": "Catalunya",
  "session_id": "s_9aee4d52a08a",
  "ts": "2026-09-15 07:00:06.371000000",
  "user_id": "u_04b42c08"
 },
 {
  "device": "web",
  "event_type": "view",
  "price_eur": 85.99,
  "product_id": "p_9dc613",
  "region": "Comunitat Valenciana",
  "session_id": "s_8e7292024915",
  "ts": "2026-09-15 07:00:13.592000000",
  "user_id": "u_9f64d903"
 }
]
```

## sample requests

`0.38s`

```sql
SELECT * FROM shop.requests ORDER BY ts DESC LIMIT 2
```

```json
[
 {
  "context.device": "web",
  "context.page": "product",
  "context.region": "Andalucía",
  "is_new_user": false,
  "recent_views": [
   {
    "product_id": "p_6d0f23",
    "ts": "2026-11-14 12:00:21.413000000"
   },
   {
    "product_id": "p_b44106",
    "ts": "2026-11-14 12:00:50.315000000"
   },
   {
    "product_id": "p_05369a",
    "ts": "2026-11-14 12:01:33.002000000"
   },
   {
    "product_id": "p_432e67",
    "ts": "2026-11-14 12:04:48.542000000"
   },
   {
    "product_id": "p_526c51",
    "ts": "2026-11-14 12:06:04.496000000"
   }
  ],
  "request_id": "r_bebc0fef86710eb1",
  "ts": "2026-11-14 12:07:25.034000000",
  "user_id": "u_c67bfe38"
 },
 {
  "context.device": "android",
  "context.page": "product",
  "context.region": "Comunitat Valenciana",
  "is_new_user": false,
  "recent_views": [
   {
    "product_id": "p_64d53d",
    "ts": "2026-11-14 12:05:37.555000000"
   },
   {
    "product_id": "p_9fb064",
    "ts": "2026-11-14 12:06:07.773000000"
   },
   {
    "product_id": "p_692114",
    "ts": "2026-11-14 12:06:08.056000000"
   },
   {
    "product_id": "p_72285d",
    "ts": "2026-11-14 12:06:48.767000000"
   }
  ],
  "request_id": "r_c964dd4dbc5d2eaf",
  "ts": "2026-11-14 12:07:24.678000000",
  "user_id": "u_9108f63d"
 }
]
```

## sample events

`0.22s`

```sql
SELECT * FROM shop.events ORDER BY ts DESC LIMIT 2
```

```json
[
 {
  "device": "android",
  "event_type": "view",
  "price_eur": 397.99,
  "product_id": "p_033d8c",
  "region": "Galicia",
  "session_id": "s_e3c34a83a282",
  "ts": "2026-11-14 12:07:25.984000000",
  "user_id": "u_74a8784f"
 },
 {
  "device": "android",
  "event_type": "view",
  "price_eur": 137.99,
  "product_id": "p_1bd9c7",
  "region": "Galicia",
  "session_id": "s_e3c34a83a282",
  "ts": "2026-11-14 12:07:25.976000000",
  "user_id": "u_74a8784f"
 }
]
```

## sample catalog_updates

`0.18s`

```sql
SELECT * FROM shop.catalog_updates ORDER BY ts DESC LIMIT 2
```

```json
[
 {
  "brand": "Tinove",
  "category": "Sports & Outdoors",
  "change": "back_in_stock",
  "created_at": "2025-01-16 07:00:00.000000000",
  "description": "Tinove Sleeping Bags with bold colours and a luxury feel.",
  "is_active": true,
  "price_eur": 19.99,
  "product_id": "p_ca886b",
  "subcategory": "Sleeping Bags",
  "ts": "2026-11-14 12:05:00.000000000"
 },
 {
  "brand": "Mipelo",
  "category": "Pets",
  "change": "back_in_stock",
  "created_at": "2025-04-10 07:00:00.000000000",
  "description": "Pet Shampoo by Mipelo, featuring designed for kids. Comes with a luxury feel.",
  "is_active": true,
  "price_eur": 41.99,
  "product_id": "p_448a0d",
  "subcategory": "Pet Shampoo",
  "ts": "2026-11-14 12:05:00.000000000"
 }
]
```

## sample feedback

`0.23s`

```sql
SELECT * FROM team_01.feedback ORDER BY ts DESC LIMIT 2
```

```json
[
 {
  "clicked": "",
  "fallback_reason": "",
  "latency_ms": 1211,
  "purchased": "",
  "request_id": "r_502fb38ea68bf6b9",
  "revenue_eur": 0,
  "served_by": "team",
  "shown": [
   "p_adc3e6",
   "p_69d40e",
   "p_0210c5",
   "p_1036d3",
   "p_e2454f",
   "p_5969fa",
   "p_2c88d5",
   "p_8ca8ed",
   "p_050730",
   "p_5733ef"
  ],
  "ts": "2026-11-14 12:07:24.881000000"
 },
 {
  "clicked": "",
  "fallback_reason": "",
  "latency_ms": 1009,
  "purchased": "",
  "request_id": "r_58f4883daad89fc8",
  "revenue_eur": 0,
  "served_by": "team",
  "shown": [
   "p_adc3e6",
   "p_69d40e",
   "p_0210c5",
   "p_1036d3",
   "p_e2454f",
   "p_5969fa",
   "p_2c88d5",
   "p_8ca8ed",
   "p_050730",
   "p_5733ef"
  ],
  "ts": "2026-11-14 12:07:24.575000000"
 }
]
```

## sample submissions

`0.20s`

```sql
SELECT * FROM team_01.submissions LIMIT 2
```

```json
[
 {
  "items": [],
  "model_version": "init",
  "request_id": "__init__"
 },
 {
  "items": [
   "p_0210c5",
   "p_09a938",
   "p_1036d3",
   "p_e2454f",
   "p_2c88d5",
   "p_55ab57",
   "p_050730",
   "p_5733ef",
   "p_d2db6a",
   "p_40ec57"
  ],
  "model_version": "baseline",
  "request_id": "r_00210588de172ae2"
 }
]
```

## describe history_sessions

`0.23s`

```sql
DESCRIBE shop.history_sessions
```

```json
[
 {
  "name": "clicked",
  "type": "Dynamic",
  "default_type": "",
  "default_expression": "",
  "comment": "",
  "codec_expression": "",
  "ttl_expression": "",
  "is_subcolumn": 1
 },
 {
  "name": "context.device",
  "type": "Dynamic",
  "default_type": "",
  "default_expression": "",
  "comment": "",
  "codec_expression": "",
  "ttl_expression": "",
  "is_subcolumn": 1
 },
 {
  "name": "context.page",
  "type": "Dynamic",
  "default_type": "",
  "default_expression": "",
  "comment": "",
  "codec_expression": "",
  "ttl_expression": "",
  "is_subcolumn": 1
 },
 {
  "name": "context.region",
  "type": "Dynamic",
  "default_type": "",
  "default_expression": "",
  "comment": "",
  "codec_expression": "",
  "ttl_expression": "",
  "is_subcolumn": 1
 },
 {
  "name": "propensity",
  "type": "Dynamic",
  "default_type": "",
  "default_expression": "",
  "comment": "",
  "codec_expression": "",
  "ttl_expression": "",
  "is_subcolumn": 1
 },
 {
  "name": "purchased",
  "type": "Dynamic",
  "default_type": "",
  "default_expression": "",
  "comment": "",
  "codec_expression": "",
  "ttl_expression": "",
  "is_subcolumn": 1
 },
 {
  "name": "recent_views",
  "type": "Dynamic",
  "default_type": "",
  "default_expression": "",
  "comment": "",
  "codec_expression": "",
  "ttl_expression": "",
  "is_subcolumn": 1
 },
 {
  "name": "request_id",
  "type": "Dynamic",
  "default_type": "",
  "default_expression": "",
  "comment": "",
  "codec_expression": "",
  "ttl_expression": "",
  "is_subcolumn": 1
 },
 {
  "name": "revenue_eur",
  "type": "Dynamic",
  "default_type": "",
  "default_expression": "",
  "comment": "",
  "codec_expression": "",
  "ttl_expression": "",
  "is_subcolumn": 1
 },
 {
  "name": "shown",
  "type": "Dynamic",
  "default_type": "",
  "default_expression": "",
  "comment": "",
  "codec_expression": "",
  "ttl_expression": "",
  "is_subcolumn": 1
 },
 {
  "name": "ts",
  "type": "Dynamic",
  "default_type": "",
  "default_expression": "",
  "comment": "",
  "codec_expression": "",
  "ttl_expression": "",
  "is_subcolumn": 1
 },
 {
  "name": "user_id",
  "type": "Dynamic",
  "default_type": "",
  "default_expression": "",
  "comment": "",
  "codec_expression": "",
  "ttl_expression": "",
  "is_subcolumn": 1
 }
]
```

## tables we can see

`0.19s`

```sql
SELECT database, name, total_rows FROM system.tables WHERE database IN ('shop', 'team_01')
```

```json
[
 {
  "database": "shop",
  "name": "catalog",
  "total_rows": 5000
 },
 {
  "database": "shop",
  "name": "catalog_updates",
  "total_rows": 912
 },
 {
  "database": "shop",
  "name": "events",
  "total_rows": 748511
 },
 {
  "database": "shop",
  "name": "history_events",
  "total_rows": 11996560
 },
 {
  "database": "shop",
  "name": "history_sessions",
  "total_rows": 2000000
 },
 {
  "database": "shop",
  "name": "requests",
  "total_rows": 33740
 },
 {
  "database": "team_01",
  "name": "feedback",
  "total_rows": 21624
 },
 {
  "database": "team_01",
  "name": "scratch",
  "total_rows": 0
 },
 {
  "database": "team_01",
  "name": "submissions",
  "total_rows": 2212
 }
]
```

## range history_sessions

`0.19s`

```sql
SELECT count() AS n, min(ts) AS first, max(ts) AS last FROM shop.history_sessions
```

```json
[
 {
  "n": 2000000,
  "first": 1789455601.456,
  "last": 1794639599.207
 }
]
```

## range history_events

`0.22s`

```sql
SELECT count() AS n, min(ts) AS first, max(ts) AS last FROM shop.history_events
```

```json
[
 {
  "n": 11996560,
  "first": 1789455606.371,
  "last": 1794640093.507
 }
]
```

## range requests

`0.19s`

```sql
SELECT count() AS n, min(ts) AS first, max(ts) AS last FROM shop.requests
```

```json
[
 {
  "n": 33742,
  "first": 1794646800.014,
  "last": 1794658047.031
 }
]
```

## range events

`0.31s`

```sql
SELECT count() AS n, min(ts) AS first, max(ts) AS last FROM shop.events
```

```json
[
 {
  "n": 748561,
  "first": 1794646800.014,
  "last": 1794658047.966
 }
]
```

## range catalog_updates

`0.19s`

```sql
SELECT count() AS n, min(ts) AS first, max(ts) AS last FROM shop.catalog_updates
```

```json
[
 {
  "n": 912,
  "first": 1794646800,
  "last": 1794657900
 }
]
```

## catalog by category

`0.21s`

```sql
SELECT category::String AS category, count() AS products, uniq(subcategory::String) AS subcats, uniq(brand::String) AS brands, round(avg(price_eur::Float64), 2) AS avg_price, countIf(is_active::Bool) AS active FROM shop.catalog GROUP BY category ORDER BY products DESC
```

```json
[
 {
  "category": "Home & Garden",
  "products": 640,
  "subcats": 9,
  "brands": 8,
  "avg_price": 44.48,
  "active": 640
 },
 {
  "category": "Pets",
  "products": 613,
  "subcats": 9,
  "brands": 8,
  "avg_price": 39.63,
  "active": 613
 },
 {
  "category": "Electronics",
  "products": 580,
  "subcats": 9,
  "brands": 8,
  "avg_price": 42.31,
  "active": 580
 },
 {
  "category": "Books & Media",
  "products": 553,
  "subcats": 9,
  "brands": 8,
  "avg_price": 57.67,
  "active": 553
 },
 {
  "category": "Toys & Baby",
  "products": 516,
  "subcats": 8,
  "brands": 8,
  "avg_price": 46.77,
  "active": 516
 },
 {
  "category": "Sports & Outdoors",
  "products": 489,
  "subcats": 9,
  "brands": 8,
  "avg_price": 35.24,
  "active": 489
 },
 {
  "category": "Home & Kitchen",
  "products": 466,
  "subcats": 9,
  "brands": 8,
  "avg_price": 62.25,
  "active": 466
 },
 {
  "category": "Computers & Gaming",
  "products": 427,
  "subcats": 9,
  "brands": 8,
  "avg_price": 40.53,
  "active": 427
 },
 {
  "category": "Fashion",
  "products": 394,
  "subcats": 9,
  "brands": 8,
  "avg_price": 62.39,
  "active": 394
 },
 {
  "category": "Beauty & Health",
  "products": 322,
  "subcats": 9,
  "brands": 8,
  "avg_price": 44.98,
  "active": 322
 }
]
```

## catalog price quantiles

`0.25s`

```sql
SELECT quantiles(0.05, 0.25, 0.5, 0.75, 0.95, 0.99)(price_eur::Float64) AS q FROM shop.catalog
```

```json
[
 {
  "q": [
   6.940000000000017,
   16.99,
   30.99,
   53.99,
   143.99,
   282.02000000000066
  ]
 }
]
```

## catalog updates by change

`0.33s`

```sql
SELECT change::String AS change, count() AS n FROM shop.catalog_updates GROUP BY change
```

```json
[
 {
  "change": "out_of_stock",
  "n": 114
 },
 {
  "change": "back_in_stock",
  "n": 78
 },
 {
  "change": "new_product",
  "n": 100
 },
 {
  "change": "price_change",
  "n": 620
 }
]
```

## history base rates

`0.39s`

```sql
SELECT count() AS n, round(100 * countIf(isNotNull(clicked) AND clicked::String != '') / count(), 2) AS ctr_pct, round(100 * countIf(isNotNull(purchased) AND purchased::String != '') / count(), 2) AS conv_pct, round(100 * countIf(isNotNull(purchased) AND purchased::String != '' AND purchased::String != clicked::String) / greatest(countIf(isNotNull(purchased) AND purchased::String != ''), 1), 2) AS bought_not_clicked_pct, uniq(user_id::String) AS users FROM shop.history_sessions
```

```json
[
 {
  "n": 2000000,
  "ctr_pct": 3.75,
  "conv_pct": 1.4,
  "bought_not_clicked_pct": 0,
  "users": 59697
 }
]
```

## history clicks by slot

`0.30s`

```sql
SELECT indexOf(shown, clicked) AS slot, count() AS clicks, countIf(isNotNull(purchased) AND purchased::String != '') AS purchases FROM shop.history_sessions WHERE isNotNull(clicked) AND clicked::String != '' GROUP BY slot ORDER BY slot
```

```json
[
 {
  "slot": 1,
  "clicks": 21483,
  "purchases": 8982
 },
 {
  "slot": 2,
  "clicks": 12015,
  "purchases": 4679
 },
 {
  "slot": 3,
  "clicks": 8805,
  "purchases": 3443
 },
 {
  "slot": 4,
  "clicks": 6836,
  "purchases": 2525
 },
 {
  "slot": 5,
  "clicks": 5629,
  "purchases": 2004
 },
 {
  "slot": 6,
  "clicks": 5043,
  "purchases": 1695
 },
 {
  "slot": 7,
  "clicks": 4438,
  "purchases": 1400
 },
 {
  "slot": 8,
  "clicks": 3923,
  "purchases": 1273
 },
 {
  "slot": 9,
  "clicks": 3483,
  "purchases": 1058
 },
 {
  "slot": 10,
  "clicks": 3260,
  "purchases": 994
 }
]
```

## history by page

`0.25s`

```sql
SELECT context.page::String AS page, count() AS n, round(100 * countIf(isNotNull(purchased) AND purchased::String != '') / count(), 2) AS conv_pct FROM shop.history_sessions GROUP BY page ORDER BY n DESC
```

```json
[
 {
  "page": "product",
  "n": 1119265,
  "conv_pct": 1.72
 },
 {
  "page": "category",
  "n": 480186,
  "conv_pct": 1.71
 },
 {
  "page": "home",
  "n": 400549,
  "conv_pct": 0.14
 }
]
```

## history by device

`0.25s`

```sql
SELECT context.device::String AS device, count() AS n, round(100 * countIf(isNotNull(purchased) AND purchased::String != '') / count(), 2) AS conv_pct FROM shop.history_sessions GROUP BY device ORDER BY n DESC
```

```json
[
 {
  "device": "ios",
  "n": 668792,
  "conv_pct": 1.25
 },
 {
  "device": "web",
  "n": 668524,
  "conv_pct": 1.38
 },
 {
  "device": "android",
  "n": 662684,
  "conv_pct": 1.57
 }
]
```

## history by region

`0.22s`

```sql
SELECT context.region::String AS region, count() AS n, round(100 * countIf(isNotNull(purchased) AND purchased::String != '') / count(), 2) AS conv_pct FROM shop.history_sessions GROUP BY region ORDER BY n DESC LIMIT 30
```

```json
[
 {
  "region": "Andalucía",
  "n": 417993,
  "conv_pct": 1.86
 },
 {
  "region": "Catalunya",
  "n": 381493,
  "conv_pct": 1.24
 },
 {
  "region": "Madrid",
  "n": 330503,
  "conv_pct": 1.24
 },
 {
  "region": "Comunitat Valenciana",
  "n": 253012,
  "conv_pct": 1.23
 },
 {
  "region": "Galicia",
  "n": 139872,
  "conv_pct": 1.19
 },
 {
  "region": "Castilla y León",
  "n": 121752,
  "conv_pct": 1.17
 },
 {
  "region": "País Vasco",
  "n": 116473,
  "conv_pct": 1.18
 },
 {
  "region": "Canarias",
  "n": 99433,
  "conv_pct": 1.76
 },
 {
  "region": "Murcia",
  "n": 70013,
  "conv_pct": 2.13
 },
 {
  "region": "Aragón",
  "n": 69456,
  "conv_pct": 0.97
 }
]
```

## history recent_views length

`0.25s`

```sql
SELECT length(recent_views) AS views, count() AS n FROM shop.history_sessions GROUP BY views ORDER BY views LIMIT 25
```

```json
[
 {
  "views": 0,
  "n": 400549
 },
 {
  "views": 1,
  "n": 500190
 },
 {
  "views": 2,
  "n": 398626
 },
 {
  "views": 3,
  "n": 300512
 },
 {
  "views": 4,
  "n": 199974
 },
 {
  "views": 5,
  "n": 119894
 },
 {
  "views": 6,
  "n": 80255
 }
]
```

## history distinct products shown

`0.23s`

```sql
SELECT uniq(arrayJoin(shown)::String) AS products_ever_shown FROM shop.history_sessions
```

```json
{
 "http": 400,
 "error": {
  "error": "rawtree_error",
  "message": "Code: 36. DB::Exception: Nullable/LowCardinality(Nullable) types are not allowed inside Variant type: while executing 'ARRAY JOIN __table1.`__raw_data.shown` :: 2 -> arrayJoin(__table1.`__raw_data.shown`) Dynamic : 0'. (BAD_ARGUMENTS) (version 26.8.39.7 (official build))",
  "hint": "Check your SQL syntax."
 }
}
```

## history propensity quantiles

`0.22s`

```sql
SELECT quantiles(0.01, 0.1, 0.5, 0.9, 0.99)(arrayJoin(propensity)::Float64) AS q FROM shop.history_sessions
```

```json
{
 "http": 400,
 "error": {
  "error": "rawtree_error",
  "message": "Code: 36. DB::Exception: Nullable/LowCardinality(Nullable) types are not allowed inside Variant type: while executing 'ARRAY JOIN __table1.`__raw_data.propensity` :: 2 -> arrayJoin(__table1.`__raw_data.propensity`) Dynamic : 0'. (BAD_ARGUMENTS) (version 26.8.39.7 (official build))",
  "hint": "Check your SQL syntax."
 }
}
```

## events by type

`0.56s`

```sql
SELECT event_type::String AS event_type, count() AS n, uniq(user_id::String) AS users, uniq(session_id::String) AS sessions, uniq(product_id::String) AS products FROM shop.history_events GROUP BY event_type
```

```json
[
 {
  "event_type": "purchase",
  "n": 548160,
  "users": 51798,
  "sessions": 464434,
  "products": 4809
 },
 {
  "event_type": "add_to_cart",
  "n": 1094353,
  "users": 55955,
  "sessions": 807604,
  "products": 4906
 },
 {
  "event_type": "view",
  "n": 10354047,
  "users": 59840,
  "sessions": 2505151,
  "products": 5000
 }
]
```

## live requests profile

`0.22s`

```sql
SELECT count() AS n, round(100 * countIf(is_new_user::Bool) / count(), 1) AS new_user_pct, round(100 * countIf(length(recent_views) = 0) / count(), 1) AS no_views_pct, round(avg(length(recent_views)), 2) AS avg_views, uniq(user_id::String) AS users FROM shop.requests
```

```json
[
 {
  "n": 33754,
  "new_user_pct": 30,
  "no_views_pct": 19.6,
  "avg_views": 2.04,
  "users": 24293
 }
]
```

## live requests by page

`0.21s`

```sql
SELECT context.page::String AS page, count() AS n FROM shop.requests GROUP BY page ORDER BY n DESC
```

```json
[
 {
  "page": "product",
  "n": 19074
 },
 {
  "page": "category",
  "n": 8080
 },
 {
  "page": "home",
  "n": 6600
 }
]
```

## live rate last 10 min

`0.24s`

```sql
SELECT (SELECT count() FROM shop.requests WHERE ts::DateTime64(3) > now() - INTERVAL 10 MINUTE) / 600 AS requests_per_s, (SELECT count() FROM shop.events WHERE ts::DateTime64(3) > now() - INTERVAL 10 MINUTE) / 600 AS events_per_s
```

```json
[
 {
  "requests_per_s": 3,
  "events_per_s": 66.645
 }
]
```

## live users known in history

`0.30s`

```sql
SELECT count() AS live_users, countIf(user_id IN (SELECT DISTINCT user_id::String FROM shop.history_events)) AS in_history FROM (SELECT DISTINCT user_id::String AS user_id FROM shop.requests WHERE NOT is_new_user::Bool)
```

```json
[
 {
  "live_users": 16359,
  "in_history": 16354
 }
]
```

## feedback summary

`0.25s`

```sql
SELECT served_by::String AS served_by, fallback_reason::String AS reason, count() AS n, round(100 * countIf(clicked::String != '') / count(), 2) AS ctr_pct, round(100 * countIf(purchased::String != '') / count(), 2) AS conv_pct, round(sum(revenue_eur::Float64) / count(), 3) AS eur_per_request, round(quantile(0.5)(latency_ms::Float64)) AS p50_ms, round(quantile(0.95)(latency_ms::Float64)) AS p95_ms FROM team_01.feedback WHERE request_id::String != '__init__' GROUP BY served_by, reason
```

```json
[
 {
  "served_by": "fallback",
  "reason": "missing",
  "n": 19509,
  "ctr_pct": 2.37,
  "conv_pct": 0.71,
  "eur_per_request": 0.124,
  "p50_ms": 0,
  "p95_ms": 0
 },
 {
  "served_by": "fallback",
  "reason": "invalid",
  "n": 2,
  "ctr_pct": 0,
  "conv_pct": 0,
  "eur_per_request": 0,
  "p50_ms": 3159,
  "p95_ms": 3301
 },
 {
  "served_by": "team",
  "reason": "",
  "n": 2131,
  "ctr_pct": 2.35,
  "conv_pct": 0.56,
  "eur_per_request": 0.123,
  "p50_ms": 1336,
  "p95_ms": 2185
 }
]
```

## insert into team_01.scratch

HTTP 200: `{"inserted":1,"elapsed_ns":"67218636","memory_usage":"38576","read_bytes":"49","read_rows":"1","result_bytes":"49","result_rows":"1","total_rows_to_read":"0","written_bytes":"49","written_rows":"1"}`

## insert into team_01.probe_marker

HTTP 400: `{"error":"rawtree_error","message":"Table probe_marker not found.","hint":"Check the table name and make sure it exists in your database."}`
