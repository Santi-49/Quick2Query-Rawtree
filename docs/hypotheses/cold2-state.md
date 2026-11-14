# cold2 · state it needs that State does not hold yet

Evidence: `H-home-ceiling.md`. cold2 reads both through `getattr`, so it runs today without them (multipliers stay 1).
Live best sellers of the last hour are **not** needed: they catch fewer organic purchases than the all-time list (5.5% vs 5.5–6.6%, top-10).

## 1. Carts not bought (history) · `Shopper.carted: dict[str, int]`
- **Why**: 16 of 24 home purchases of returning shoppers; ×14–54 over never-seen live, ×38 in history. 96% of returning home requests have one.
- **Source**: add `countIf(event_type::String = 'add_to_cart') AS c` and `groupArray(c) AS carts` to `sql/features/user_products.sql`;
  `data.user_history()` stores a `carts` uint8 array next to `views` / `buys` (clip 255).
- **Refresh**: static, rebuilt by `q2q pull` (history does not change). Today's `add_to_cart` events (item 2) add +1.
- **Memory**: one uint8 per (user, product) pair already held: a few MB.
- **State.shopper()**: `carted = {pid: c for pid with c > 0 and b == 0 and pid not in live purchases}` (+ today's carts).
- **cold2 use**: `cart` multiplier ×5, ×10 if carted twice or more; carts are always candidates; `viewed before` (×1.5) only applies to products never carted.

## 2. Today's views and carts · `State.today_views(user_id) -> list[str]`
- **Why**: 88% of returning and 91% of new-shopper home requests follow organic views earlier today (recent_views only covers the current session).
  New shoppers: product viewed today 0.96% per weighted impression (2 buys), its subcategory 0.42% (7 buys) vs 0.09–0.13% otherwise.
- **Source**: incremental, like `_purchases`: `SELECT user_id::String AS u, product_id::String AS p, event_type::String AS et, toString(ts::DateTime64(3)) AS ts
  FROM shop.events WHERE event_type::String IN ('view', 'add_to_cart') AND ts::DateTime64(3) > toDateTime64('{last}', 3) - INTERVAL 3 SECOND`.
- **Refresh**: every 5 s (≈ 300 rows per call at 240k events per hour). Load: the last 2 hours at start.
- **Memory**: per user a list of the last 10 distinct viewed products (newest last); drop users idle for 2 hours. ~65k users × 10 refs ≈ 30–40 MB.
- **cold2 use**: `today` multiplier ×4 for a product viewed today, ×3 for its subcategory; those products and the top of their subcategories are candidates.
  Today's carts feed `Shopper.carted` (needs `shopper()` to return a Shopper for a new user with today's carts only).

## Also
- Add `"cold2": "agate"` to `PUBLIC` in `strategy.py` before deploying, or its label is a hash.
