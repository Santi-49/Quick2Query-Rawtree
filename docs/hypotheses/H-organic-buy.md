# H-organic-buy · purchase model fitted on the organic stream (ranker7)
- **status**: rejected offline. Organic alone is worse; the geometric blend ties. `ranker7` not promoted.
- **owner**: agent, 14 Nov night
- **code**: `src/q2q/train7.py`, `src/q2q/strategies/ranker7.py`, `eda/replay/holdout67.py`, `eda/replay/timing67.py`, `tests/test_ranker7.py`

## Claim
`shop.events` has over 100,000 purchases today against our ~1,000. A purchase model fitted on organic
purchase-after-view, with ranker2's features as of the view, replaces or strengthens ranker2's noisy buy-given-click model.

## Test
Rows (train7): one per (shopper, product viewed today), at the last view before the first purchase of that product
(label 1) or at its last view (label 0). Views in the 30 minutes before the cut open no row; products already bought
are skipped. Positives from every shopper, negatives from 1/16 of shoppers (`cityHash64 % 64 < 4`). Features:
ranker2's, as of the view: the session's earlier views as recent views (last 6), earlier views today, history-only
shopper features (`live=False`), slot 1, page `product`. Pulled in 16 user-hash chunks (about 46,000 events each,
1.5 s). LightGBM with ranker2's params, early stopping on the newest 20% by view time, refitted on everything.
Serving: ranker2's click model x ranker2 buy^(1 − α) x organic^α; α = 1 (`ranker7`) and α = 0.5 (`ranker7h`).
Evaluation: holdout3 method, every model fitted before 18:28:32 UTC, replay 18:28–21:28 UTC (574 purchases).

## Result
**Only ~7.5% of organic purchases follow a view of the same product by the same shopper today** (143 of 1,916 on a
1/64 user sample; 43 in the same session). Most organic purchases have no view before them. Before the cut:
106,193 rows, 4,574 purchases after a view (4.7x our 964). Organic AUC on its own newest 20%: 0.868 (1,418 rounds).
Importance: appeal 25%, cat_carts 14%, log_buys 10%, phrase_share 9%, shopper_cart_rate 8%. `in_views` is not in
the top 10; in our clicks it is the strongest buy signal.

Transfer to our clicks (buy given click AUC, newest 20% of our clicks, 878 clicks, 258 purchases; the organic model
never saw a click): ranker2 buy fitted on the oldest 80% **0.681**, organic **0.594**, geometric blend 0.671. Organic on
all 3,101 clicks: 0.614.

Paired candidate − ranker2, same requests (points, ± bootstrap se, n):

| | route | hit1 | hit3 | hit10 | hit10 not logged by ranker2 |
|---|---|---|---|---|---|
| ranker7 (α 1) | main (321) | −2.5 ± 2.2 | −3.4 ± 2.2 | **−5.3 ± 1.8** | −1.5 ± 2.5 (131) |
| | new_shopper (225) | −2.7 ± 2.9 | **−6.2 ± 2.6** | **−4.4 ± 2.0** | +0.0 ± 2.8 (100) |
| ranker7h (α 0.5) | main | −0.9 ± 1.8 | +1.2 ± 1.7 | −1.2 ± 1.3 | −0.8 ± 1.7 |
| | new_shopper | +1.3 ± 2.4 | −2.2 ± 2.0 | −0.4 ± 1.4 | +2.0 ± 1.9 |

organic10 (no_views, 471): ranker7 +0.0 ± 0.7, ranker7h +1.1 ± 0.6.
Compute in the replay: ranker2 12 ms, ranker7 / ranker7h 47 ms per request (the organic model has 1,418 rounds).

## Verdict
- **Does not transfer.** Organic purchase-after-view is a different event from purchase after a click on our list:
  it is rare (7.5% of organic purchases), takes hours rather than minutes, and is driven by product popularity and the
  shopper's cart habits, while purchase after our click is driven by the session (re-viewed product, `in_views`).
  On our clicks it ranks worse than ranker2's own buy model (0.594 against 0.681).
- α = 1: **worse** (hit10 −5.3 main, hit3 −6.2 new shoppers, over two se). α = 0.5: **tie** on every hit line;
  organic10 +1.1 ± 0.6 on home is a small lean, not a win, and the blend costs 4x the compute (over the 15 ms budget).

## Next
- None for the main route. If home matters: try the organic model on the no_views route only, capped to ~200 rounds.
