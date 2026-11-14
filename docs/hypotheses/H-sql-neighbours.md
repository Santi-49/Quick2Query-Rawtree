# H-sql-neighbours · session nearest neighbours asked of RawTree per request
- **status**: rejected offline, 14 Nov 22:30 UTC. `knn1` built, not queued.
- **owner**: agent, 14 Nov evening
- **code**: `src/q2q/strategies/knn1.py`, `eda/replay/knn1.py`, `tests/test_knn1.py`

## Claim
Other shoppers who viewed the same products today carted or bought something; asking `shop.events` for those
products at request time adds a live signal that the trained rankers do not have, and fusing it with ranker2's list
(reciprocal rank fusion, as blend1) lifts the purchased product.

## Test
`knn1`: one query per request with recent views: sessions of other shoppers that viewed one of the views in the last
12 h, weight = sum over the views they share (the newest view counts 2x the oldest), and the products those sessions
carted (1) or bought (2x), top 20. Fused with ranker2's top 10, K 10. Timeout, error or empty result: ranker2's list.
`as_of = True` restricts the query to events before `req.ts` (replay).

Replay on the cached 3 h holdout window (18:28 to 21:28 UTC, as holdout3 and H-blend), ranker2 and blend1 with the
holdout models fitted before the window. Two request sets, both with recent views:
- **shown**: 546 requests where a shown product was bought (321 ordinary, 225 new shoppers). Biased towards the arm
  that logged the list (ranker2 315, rules5 231): a list that never ran scores low.
- **organic**: 500 sampled requests followed within 30 min by an organic purchase of a product we did not show.

Query variants were scored in Python from one wide pull per request (every matched cart or purchase with its views
and age): windows 3 h / 12 h / today, purchase weight 1 / 2 / 4, time decay, recent-view weight, keeping or excluding
the shopper's own views, popularity lift, and 7 days of `shop.history_events` co-carts.

## Result
Hit rate %, ± se; d = paired difference against ranker2 ± bootstrap se.

| shown, ordinary (321) | top 1 | top 3 | top 10 | d top 1 | d top 3 |
|---|---|---|---|---|---|
| ranker2 | 33.6 ± 2.6 | 60.1 ± 2.7 | 87.5 ± 1.8 | | |
| blend1 | 30.2 ± 2.6 | 59.2 ± 2.7 | 89.1 ± 1.7 | -3.4 ± 2.3 | -0.9 ± 2.3 |
| neighbour list alone | 9.3 ± 1.6 | 16.5 ± 2.1 | 31.5 ± 2.6 | -24.3 ± 2.9 | -43.6 ± 3.3 |
| knn1 w 0.15 | 33.6 ± 2.6 | 60.1 ± 2.7 | 87.5 ± 1.8 | +0.0 ± 1.4 | +0.0 ± 1.2 |
| knn1 w 0.3 | 31.8 ± 2.6 | 59.8 ± 2.7 | 87.5 ± 1.8 | -1.9 ± 2.2 | -0.3 ± 1.6 |
| knn1 w 0.6 | 28.7 ± 2.5 | 57.6 ± 2.8 | 85.0 ± 2.0 | -5.0 ± 2.6 | -2.5 ± 2.0 |

| shown, new shoppers (225) | top 1 | top 3 | top 10 | d top 1 | d top 3 |
|---|---|---|---|---|---|
| ranker2 | 35.6 ± 3.2 | 66.7 ± 3.1 | 84.9 ± 2.4 | | |
| blend1 | 39.1 ± 3.3 | 65.3 ± 3.2 | 88.9 ± 2.1 | +3.6 ± 2.7 | -1.3 ± 2.5 |
| neighbour list alone | 18.7 ± 2.6 | 32.4 ± 3.1 | 48.0 ± 3.3 | -16.9 ± 3.2 | -34.2 ± 3.7 |
| knn1 w 0.15 | 36.0 ± 3.2 | 66.7 ± 3.1 | 84.9 ± 2.4 | +0.4 ± 1.2 | +0.0 ± 1.4 |
| knn1 w 0.3 | 36.4 ± 3.2 | 62.7 ± 3.2 | 84.9 ± 2.4 | +0.9 ± 2.4 | -4.0 ± 2.2 |
| knn1 w 0.6 | 33.3 ± 3.1 | 56.9 ± 3.3 | 85.8 ± 2.3 | -2.2 ± 3.0 | -9.8 ± 3.0 |

Organic set, top 10, ordinary (424): ranker2 3.8 ± 0.9, blend1 3.8 ± 0.9, neighbour list alone 4.7 ± 1.0
(paired +0.9 ± 1.4), knn1 w 0.3 3.8, w 0.6 4.5 (+0.7 ± 0.6). New shoppers (76): ranker2 and every fusion 0 hits,
neighbour list 1 hit. Top 1 and top 3 under 2.5% for everything.

- Excluding the shopper's own views from the neighbour list (the first design) is clearly worse: alone 3.1 / 8.9 top 1,
  and fused at w 0.3 it costs 6.5 ± 1.9 (ordinary) and 12.0 ± 2.7 (new) points of top 1, because it pushes products
  ranker2 ranks below a viewed product above it. Shoppers buy what they viewed.
- Window: 3 h a little worse than 12 h; 12 h equals all of today. Purchase weight, decay and the recent-view weight move
  nothing beyond noise. Popularity lift (count / carts^0.5) is much worse. 7 days of history co-carts alone are below
  today's list and add nothing to it.
- Coverage: 100% of requests with views get 5+ products (99% 10+ even at 3 h): the list is never empty, it is mostly
  the day's best sellers that share a session with the views.

Latency of the final query (12 h, keep seen), 40 runs from the laptop, distinct requests: client median 351 ms, p90
422, p95 506, max 752 (1 of 40 over 600 ms); RawTree server time median 147, max 344; gateway median 224. `SELECT 1`
alone costs median 204 ms, max 571. The 12 h window reads 5.76 M rows (the whole table twice: the `ts` filter prunes,
but 12 h is almost all of today); 3 h reads a quarter (median 307 ms, max 824 over 30 runs). Slow runs are network
and gateway jitter, not the query: server time stays under 350 ms; a repeat of the same requests is no faster (no cold
cache effect on `shop.events`). `LIMIT 500` recent sessions made it slower (median 357, max 1,031); a single-scan
`GROUP BY session` form and an `IN (subquery)` form are equal within noise. `shop.history_events` 7 days: 70 to 450 ms
server (cold first run), 60 days 550 ms server: too slow per request.

## Verdict
Worse than blend1 and at best a tie with ranker2. At fusion weights high enough to change the list (0.3+) it costs top
1 or top 3; at 0.15 it changes almost nothing. The neighbour list alone is far below ranker2 on the shown set and
within noise of it on the organic set. The signal it carries (what is bought with these views today) is already in
ranker2's co-view, trend and popularity inputs.

## Next
- Not queued. If revisited, not as a per-request query: the router answers requests one at a time in its poll loop
  (`serve.py`), so 350 ms per request would back up the queue at about 3 requests per second unless run in parallel.
- A co-cart table precomputed every few minutes into the State (one query, not one per request) would test the same
  signal at no latency cost, as a ranker input rather than a fused list.
