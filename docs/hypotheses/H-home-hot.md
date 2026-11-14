# H-home-hot · home page ranked with what converts right now (SQL aggregates, not per-request SQL)
- **status**: rejected offline, 14 Nov 23:00 UTC. `hot1` built, not queued.
- **owner**: agent, 14 Nov evening
- **code**: `src/q2q/strategies/hot1.py`, `tests/test_hot1.py`, `eda/replay/hot_pull.py`, `eda/replay/hot1.py`

## Claim
On home requests (no recent views, 19% of traffic) cold2's all-time best sellers can be beaten by signals refreshed
every few minutes from RawTree: (1) live purchases and carts per product (conversion-weighted, by region / device),
(2) the shopper's history beyond what cold2 uses (subcategory or category bought before, subcategory and brand shares),
(3) our own purchase rate per impression on home lists.

## Test
`eda/replay/hot_pull.py` pulls every home request of 14 Nov 09:30 to 22:32 UTC with a feedback row (26,647), their
shoppers' purchases, views and carts, and shop.events counts per product per 10 minutes (overall; carts and purchases
also per region and device). Replay as knn1.py: State as of each request (live purchases, today's views and carts),
live counts as of the last complete 10-minute bucket. Two sets: **shown** (106 requests, a shown product bought; biased
to the arm that logged the list) and **organic** (2,506 requests followed within 30 min by an organic purchase of a
product we did not show). cold2 and ranker2 (holdout models fitted before 18:28) replayed and cached.

Screening (all day, hit top 1/3/10, cold2 = shown ret 32/58/84, new 20/48/82, organic ret 0.3/1.6/4.9, new 0.7/1.5/2.7):
- **Live, non-personal lists alone** (buys last 30/60/120 min, carts, buys per view, all-time) catch 1.0–1.3% of
  returning organic purchases at top 10 against 4.9% for cold2. As a multiplier on cold2: live buys per view, shrunk
  (20 pseudo-views), ×1/3..×3 (`conv`) gives +3 to +6 points on shown, nothing on organic. Live buys over the all-time
  share, cart lift, region lift, 30/60/240 min windows, exponents 0.5–2: all within ±1 point of `conv` or worse.
- **Our home feedback rate** (purchases or clicks per slot-weighted impression, shrunk): worse alone (27% shown top 10)
  and as a multiplier (new shoppers' shown top 10 −18 points at ×1).
- **History**: subcategory bought before ×3 and subcategory view share (1 + 5 × share) lift organic top 10 by ~1 point;
  category bought ×2, brand share, extra candidates from top / bought subcategories: nothing.
- **ranker2 × conv** or × bought subcategory: no change to ranker2.
- What the organic purchases are (returning, 2,910 products): 29% bought in history, 9% bought earlier today (no list
  can show them: bought products are never shown, and the carousel never sells them, H-home-personal), 7% carted in
  history, 1% carted today, 20% viewed in history only, 34% untouched. 55% of all of them sit in a category the shopper
  bought in before. New shoppers: 95% untouched.

`hot1` = cold2 × conv (120 min) × subcategory bought ×3 × (1 + 5 × subcategory share); "conv only" = cold2 × conv.

## Result
Paired difference, points ± bootstrap se. Parameters were picked on the whole day, so no window is clean for hot1;
ranker2 is in-sample before 18:28.

| all day | n | hot1 − cold2 top 1 / 3 / 10 | hot1 − ranker2 top 1 / 3 / 10 | conv only − cold2 top 1 / 3 / 10 |
|---|---|---|---|---|
| shown, returning | 62 | +0.0±4.1 / +3.2±5.0 / −3.2±3.3 | −16.1±7.2 / −11.3±6.5 / −6.5±5.1 | +3.2±2.2 / +4.8±4.1 / +1.6±1.6 |
| shown, new | 44 | +2.3±2.3 / −2.3±4.8 / +0.0±3.2 | −2.3±6.7 / −4.5±7.6 / +11.4±6.7 | +4.5±3.2 / +2.3±2.2 / +4.5±3.3 |
| shown, all | 106 | +0.9±2.4 / +0.9±3.7 / −1.9±2.3 | −10.4±5.1 / −8.5±4.8 / +0.9±4.1 | +3.8±1.9 / +3.8±2.7 / +2.8±1.6 |
| organic, returning | 2,054 | +0.1±0.1 / +0.2±0.2 / **+1.0±0.3** | −0.3±0.2 / −0.7±0.3 / −0.7±0.5 | +0.0 / +0.1 / +0.1±0.2 |
| organic, new | 452 | +0.2±0.2 / +0.2±0.5 / **+2.4±0.7** | −0.2±0.6 / −0.4±0.6 / +0.0±0.9 | +0.2 / +0.4 / +0.2±0.5 |
| organic, all | 2,506 | +0.2±0.1 / +0.2±0.2 / **+1.2±0.3** | −0.3±0.2 / **−0.7±0.3** / −0.6±0.4 | +0.1 / +0.2 / +0.1±0.2 |

Levels, organic all, top 10: cold2 4.5%, ranker2 6.3%, hot1 5.7%, conv only 4.6% (requests with a target a list can
show: 5.7 / 8.0 / 7.3 / 5.9%). From 18:28 (ranker2 out of sample): organic all top 10 hot1 − cold2 +1.1 ± 0.4,
hot1 − ranker2 −1.0 ± 0.8; shown (42) everything within ±5 ± 8.

Compute: hot1 2.0 ms per request (conv only 1.5; cold2 ~2.3, ranker2 ~9 in the same replay). Refresh query
(per-product views and purchases over 120 min) 0.5 s from the laptop, 5,400 rows, every 5 min in a daemon thread.

## Verdict
- The live signals do not carry the home page. Conversion-weighted live popularity sharpens which best seller goes
  first among products shown and bought (+3.8 ± 1.9 top 1, 106 purchases: weak) and does nothing on organic purchases.
  Region, device, carts, windows and our own home feedback add nothing.
- The organic gain of hot1 over cold2 (+1.2 ± 0.3 top 10, both halves of the day) comes from history (subcategory
  bought before, subcategory share), not from anything live.
- hot1 stays below ranker2 on organic purchases (−0.7 ± 0.3 top 3, −0.6 ± 0.4 top 10) and on shown top 1 of returning
  shoppers. ranker2 already ties cold2 live. **Reject**: do not queue hot1. If the home arms change, the offline
  evidence favours ranker2 alone over cold2 there.

## Next
- If cold2 stays an arm, its cheapest improvement is the two history parts (subcategory bought ×3, subcategory share),
  no SQL needed; worth a line in ranker2's inputs instead (it has `sub_share`, not "bought in this subcategory").
- 38% of returning shoppers' organic home purchases are of products already bought: unreachable by rule. If the
  simulator ever sold a bought product from the carousel, that would be the largest home lever; H-home-personal says
  it does not (0 clicks in 3,590 impressions).
