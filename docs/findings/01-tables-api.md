# 01 · Tables, API and what our key may do

Measured Saturday 14 Nov, 12:00–12:30 UTC. Raw samples: `00-probe.md`. Queries: `scripts/probe.py`, `eda/00-syntax.sql`.

## Tables

| Table | Rows | Time range (UTC) | Columns |
|---|---|---|---|
| `shop.catalog` | 5,000 | static snapshot | product_id, category, subcategory, brand, price_eur, description, created_at, is_active |
| `shop.catalog_updates` | ~1,000 after 3.5 h | live, `ts` on a 5-minute grid | `change` (new_product, price_change, out_of_stock, back_in_stock) + the full product record |
| `shop.history_sessions` | 2,000,000 | 15 Sep 07:00 → 14 Nov 07:00 | request_id, ts, user_id, context.page/device/region, recent_views, shown, propensity, clicked, purchased, revenue_eur |
| `shop.history_events` | 11,996,560 | same | ts, user_id, session_id, event_type (view, add_to_cart, purchase), product_id, price_eur, device, region |
| `shop.requests` | 10,800 per hour | live since 14 Nov 09:00 | request_id, ts, user_id, is_new_user, context.*, recent_views |
| `shop.events` | ~240,000 per hour | live | as `history_events` |
| `team_01.submissions` | ours | | request_id, items, model_version |
| `team_01.feedback` | one per request | a few seconds behind the request | request_id, ts, shown, served_by (team, fallback), fallback_reason (missing, late, invalid), latency_ms, clicked, purchased, revenue_eur |
| `team_01.scratch` | ours | | free-form JSON |

- `shop.catalog` never changes. New products exist only in `catalog_updates`. **We must keep the catalogue state ourselves.**
- `recent_views` entries hold only `product_id` and `ts`. No `session_id` in the carousel tables.

## SQL that works

Every column is `Dynamic`. Cast before use: `x::String`, `ts::DateTime64(3)`, `shown::Array(String)`, `propensity::Array(Float64)`, `recent_views::Array(JSON)`, `is_new_user::Bool`.

- `arrayJoin(shown::Array(String))`, `arrayMap(v -> v.product_id::String, recent_views::Array(JSON))`, `(recent_views::Array(JSON))[-1].product_id::String`.
- `clicked` and `purchased` are NULL in history when nothing happened and `''` in feedback.
- **An unmatched LEFT JOIN row returns defaults (0, `''`, 1970), not NULL.** Test with `n = 0` or `x != ''`.
- Window functions, scalar subqueries, `UNION ALL`, `quantilesExact`, `argMax`, joins to the catalogue all work.

## Speed and limits

| | |
|---|---|
| Aggregate over 2M or 12M rows | 0.2–0.6 s |
| Join of 20M impressions with user history | 1–5 s |
| Query time limit | 30 s |
| Result size, query body | 100 MiB, 50 MiB |
| Insert body, insert rate | 100 MiB, 1,000 per second per table |
| Query rate | 10,000 per second per database |

No practical limit for us. Features can be computed in RawTree on demand.

## What our key may do

| Action | Result |
|---|---|
| Query `shop.*` and `team_01.*`, list tables | yes |
| Insert into `submissions` and `scratch` | yes |
| `CREATE TABLE` | 403 |
| `INSERT ... SELECT` | 403 |
| Insert into a table that does not exist | 400 |
| Workflows (scheduled SQL), keys, databases, logs endpoints | 403 |

- **All our tracking goes into `team_01.scratch` with a `kind` field.**
- Scheduled SQL is our own timer running SQL files.
- No read-only key for a public dashboard unless the organisers issue one.

## Timing from the laptop (Barcelona, university network)

| | |
|---|---|
| Network round trip to `api.rawtree.com` (AWS) | ~110–130 ms, which fits the US East coast |
| `SELECT 1` | median 207 ms, min 183, max 801 |
| Starter-shaped poll for new requests | 240 ms |
| Request visible in `shop.requests` after its `ts` | 130–620 ms, typically 390 |
| Starter answer latency | p50 1.4–1.5 s, p95 2.3 s, p99 2.7 s, max 3.5 s |

- The deadline is 3 s. The starter's p99 is 0.3 s away from it.
- Two network round trips sit inside every answer. A machine next to RawTree would remove about 0.4 s.
