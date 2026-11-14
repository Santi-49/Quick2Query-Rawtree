# H-embeddings · ranker2 plus learnt product embeddings

- **Status:** rejected offline; `ranker5` built, not queued.
- **Owner:** agent, 14 Nov night
- **Code:** `sql/features/emb_pairs.sql`, `src/q2q/emb.py`, `src/q2q/strategies/ranker5.py`, `src/q2q/train5.py`, `eda/replay/holdout5.py`, `tests/test_ranker5.py`

## Claim
Stronger teams seem to use collaborative filtering. ranker2 sees co-views only as raw "b right after a" counts. A dense
product embedding learnt from what shoppers touch together gives similarity to the session, the last view, the
shopper's history and today's views for every product, plus better candidates, and lifts the purchased product.

## Test
- Embedding: products touched (view, cart, purchase) by one shopper on one day, 30 days of `shop.history_events` plus
  `shop.events` before the cut; user-days with 2 to 50 products; ordered pairs with n ≥ 2, 16 hash chunks (13.8 M pairs,
  31 s). PPMI with context smoothing 0.75 on the 5,000 most connected products, truncated SVD (scipy `svds`), 32 dims,
  U·√S, rows L2-normalised. The 10 nearest neighbours share the subcategory 93% of the time, the category 97%.
- Five inputs added to ranker2's, cosine of the candidate to: mean of recent views, closest recent view, last view, mean
  of the shopper's history purchases and carts (today's carts left out at serving, as in training), mean of today's
  earlier views. NaN when either side has no embedding. Candidates: ranker2's plus the 30 nearest neighbours of the
  recent views' mean. Same rows and recipe as train2 (train3's `fit`).
- Leak-free replay as holdout3: window 18:28–21:28 UTC 14 Nov (574 purchases, 2,500 organic), ranker2 and ranker5
  fitted on feedback before 18:28 and the embedding built from events before 18:28; models in `data/replay/models5/`.

## Result
train5's own split (newest 20%, 258 requests with a purchase): click AUC 0.829 → 0.834, buy given click 0.679 → 0.687,
but purchased product first 39.1 → 37.2%, top 3 67.4 → 63.2%. The trees use the cosines (click gain: emb_profile 7.5%,
emb_mean_recent 7.4%, emb_today 6.9%; buy: emb_today 9.0%, emb_mean_recent 7.9%).

Paired ranker5 − ranker2, points, same requests (± bootstrap se, n). `_notr2` = requests ranker2 did not log:

| route | hit1 | hit3 | hit10 | hit1_notr2 | hit3_notr2 | hit10_notr2 | organic10 |
|---|---|---|---|---|---|---|---|
| main | −2.5 ± 2.0 | −2.8 ± 2.4 | **−4.4 ± 1.8** | −1.5 ± 2.8 | +0.0 ± 3.6 | +0.8 ± 2.3 | **+0.9 ± 0.4** |
| new_shopper | +1.3 ± 3.1 | **−12.4 ± 3.1** | −4.0 ± 2.2 | +4.0 ± 4.3 | **−15.0 ± 4.7** | −1.0 ± 3.3 | +1.1 ± 0.9 |
| no_views | +7.1 ± 7.1 (28) | +3.6 ± 6.0 | +3.6 ± 6.3 | | | | +0.4 ± 0.7 |

A first run on the same models gave the same signs (no_views organic10 +1.3 ± 0.7). Overlap with the logged list
falls from 55% to 46%: the neighbour candidates displace products ranker2 would show. Replay compute (laptop,
through guard): ranker2 22.7 ms, ranker5 25.8 ms per request. Embedding file 640 KB (5,000 × 32 float32) plus a
5,000-id list; a 5,000 × 5 float32 similarity table (100 KB) per request.

## Verdict
- Worse. Hit10 on the main route loses 4.4 ± 1.8 and hit3 on new shoppers loses 12 to 15 points, also on requests
  ranker2 did not log. On those other-arm requests main is a tie.
- The one gain is organic10 (+0.9 ± 0.4 main, about 2 se): embeddings find more of what shoppers buy on their own,
  which this metric partly rewards as popularity.
- The embedding mostly restates subcategory (93% of neighbours), which ranker2 already has; the new candidates cost
  more than the cosines add.

## Next
- Not worth live traffic as built. If retried: the cosines without the neighbour candidates, and the new-shopper route
  left on ranker2.
