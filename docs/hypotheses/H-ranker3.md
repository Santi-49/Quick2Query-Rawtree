# H-ranker3 · ranker2 plus today's carts and the H-loglinear inputs
- **status**: mixed offline; `ranker3` queued, not promoted.
- **owner**: agent, 14 Nov evening
- **code**: `src/q2q/train3.py`, `src/q2q/strategies/ranker3.py`, `eda/replay/holdout3.py`, `eda/replay/timing3.py`, `tests/test_ranker3.py`

## Claim
ranker2 trains with `live=False`, so it never learnt today's carts, the largest miss in H-gap (1.7% / 6.4% per weighted
impression against 0.7% / 1.2% for the first view). Adding them, and the H-loglinear inputs, as request-time
features lifts the purchased product into the top 3.

## Test
Rows as train2, plus 10 inputs taken strictly before each request: `carted_today` (times, not bought since),
`mins_since_cart_today`, `cat_carted_today`, `sub_carted_today` (other today-carted products in the same category and
subcategory), `clicked_ours_today`, `single_view_session`, `n_recent_views` (distinct), `log_appeal`, `log_bpv`
(log (buys + 3.4) / (views + 20)), `cart_x_high_cart_rate` (history cart and cart rate ≥ 0.08). `carted_not_bought` is
history only at serving too (ranker2 sees today's carts in it live but not in training). Products bought earlier today
are left out of training, as serving never shows them. `page` was already an input. Candidates: ranker2's plus every
product carted today, not bought, in stock.

## Result
Today-cart rows in training: before 15:32 UTC 1,931 impressions, 63 clicks, 37 purchases; to 18:30 UTC 13,355
impressions, 242 clicks, 116 purchases (0.87% per impression against 0.10%). Above 30 purchases, so no hand prior
(`CART_PRIOR = 1.0`).

Newest 20% by time, every candidate at slot 1 (train3's own split):

| fit | rows | click AUC r2 / r3 | buy given click AUC r2 / r3 | first % r2 / r3 | top 3 % r2 / r3 |
|---|---|---|---|---|---|
| before 15:32 | 110 requests | 0.853 / 0.856 | 0.767 / 0.774 | 45.5 / 50.0 | 73.6 / 79.1 |
| to 18:30 | 271 requests | 0.821 / 0.838 | 0.700 / 0.712 | 38.7 / 42.1 | 62.4 / 70.8 |

Leak-free replay, window 15:32–18:32 UTC (465 purchases, 2,500 organic), ranker2 and ranker3 fitted before it:

| strategy | main hit1 | main hit3 | main hit10_other | new hit1 | new hit3 | new hit10_other | no_views organic10 |
|---|---|---|---|---|---|---|---|
| rules5 | 24.4 ± 2.8 | 47.4 ± 3.0 | 78.2 ± 2.6 | 25.5 ± 3.3 | 48.5 ± 3.9 | 81.0 ± 3.2 | 3.0 ± 0.8 |
| ranker2 | 28.9 ± 2.9 | 51.1 ± 3.3 | 79.0 ± 2.9 | 28.5 ± 3.7 | 50.3 ± 4.1 | 78.6 ± 3.2 | 6.1 ± 1.1 |
| ranker3 | 28.1 ± 2.8 | 52.2 ± 3.0 | 78.9 ± 2.6 | 26.7 ± 3.5 | 53.3 ± 3.9 | 80.0 ± 3.0 | 5.1 ± 1.0 |

Paired ranker3 − ranker2, same requests: main hit1 −0.7 ± 1.9, hit3 +1.1 ± 2.2; new hit1 −1.8 ± 3.5, hit3 +3.0 ± 3.4;
hit10 on requests logged by neither ranker2 nor rules5: main −4.9 ± 2.0 (183), new −1.6 ± 3.0; organic10 −1.0 ± 0.8.
ranker3's hit10_other counts every request (it never logged), ranker2's leaves out its own: compare the paired lines.

On the 71 purchases of a product carted today: hit1 / hit3 / hit10 rules5 72 / 96 / 100, ranker2 30 / 46 / 76,
ranker3 48 / 73 / 92. With a ×3 cart prior ranker3 reached 68 / 93 / 97 there, but its overall hit3 fell to 50.3.

Importance (gain, click model to 18:30): slot 14.2%, phrase_share 13.2%, shopper_cart_rate 13.0%,
cart_x_high_cart_rate 5.9%, cat_carts 5.6%, cat_share 4.3%, appeal 4.2%, cat_carted_today 4.1%, in_main_cat 3.8%,
brand_share 3.7%, coview 3.5%, segment 2.9%.

Shadow timing, 300 newest live requests, read-only: ranker3 median 5.8 ms, p95 8.4 ms, 0 invalid lists; slot 1 is
a today cart on 43 of 237 requests with any cart today (ranker2 23).

## Verdict
- The trees did learn today's carts (cart-purchase hit1 30 → 48%), and the time split gains 8 points of top 3 on
  the newest data, but the leak-free replay shows no gain overall and a loss of hit10 on other arms' requests
  (−4.9 ± 2.0, main). Not enough to replace ranker2.
- Cart purchases are 15% of purchases; rules5 catches them best, and forcing them up costs elsewhere.
- The holdout model saw only 37 today-cart purchases; the current one 116. A replay window after 18:30 would test
  the stronger model.

## Next
- State: cart times and our clicks today (see the report), then replay again on a window after 18:30.
- Try ranker3 on new shoppers only, where hit3 is +3.0.
