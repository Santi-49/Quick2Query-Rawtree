# H-loglinear · the simulator's score is a product of a few clean factors

- **Status:** rejected as a ranker; kept as a reading of the factor sizes
- **Owner:** agent (log-linear fit), 14 Nov evening
- **Code:** `eda/linear/fit.py` (output `data/linear/out.txt`), `src/q2q/strategies/linear1.py` (not promoted), `eda/linear/timing.py`

## Claim
The hidden model multiplies a product's base appeal by a few round factors (session, cart, taste, slot). If so, an L2
logistic regression on 37 clean 0/1 indicators (plus log appeal) recovers stable coefficients near round multipliers and
ranks as well as ranker2's LightGBM, while generalising better to the final's new shoppers and products.

## Test
Rows as `train2`: one per shown product per feedback request to 17:40 UTC 14 Nov, history-bought products left out:
796,243 rows, 2,705 clicks, 854 purchases, 81,868 requests. Today's views, our earlier clicks, today's purchases and
price cuts at request time. Click and purchase-given-click fitted on all rows and on each half by time ("stable" means the
two halves are within 25%). Held out: newest 20% of requests (229 with a purchase), every candidate scored at slot 1.

## Result: multipliers exp(coef) on the odds, all rows (half 1 / half 2)

| Indicator | Click | Stable | Buy given click | Stable |
|---|---|---|---|---|
| slot 2 / 3 / 4 / 5 | 0.54 / 0.47 / 0.38 / 0.33 | yes | 1.13 / 0.87 / 0.70 / 1.05 | mostly |
| slot 6–10 | 0.21–0.26 | 7, 8, 9 yes | 0.87–1.44 | no |
| log appeal (per log unit) | 4.49 (3.81 / 4.42) | yes | 3.03 | yes |
| in recent views | 1.31 | yes | 1.31 | no |
| first recent view | 2.43 (3.05 / 2.21) | no | 1.64 | no |
| session main category | 2.11 | yes | 1.65 | yes |
| same subcategory as a view | 1.09 | yes | 0.94 | yes |
| subcategory viewed today | 1.76 | yes | 1.18 | yes |
| viewed today, outside session | 1.16 | no | 1.48 | yes |
| carted, not bought | 1.03 | yes | 0.85 | yes |
| carted × high cart rate (≥ 0.081) | **2.50** | yes | 1.96 | no |
| carted twice or more | 1.37 | no | 0.66 | yes |
| viewed before, never carted | 1.00 | no | 0.56 | yes |
| shopper's top / 2nd / 3rd / other category (vs never) | 0.66 / 0.38 / 0.29 / 0.15 | other only | 1.06 / 0.51 / 0.44 / 0.42 | top 2 |
| phrase share 0.22–0.30 / 0.30–0.38 / > 0.38 | 1.40 / 2.69 / **5.13** | no | 1.30 / 2.13 / 4.55 | > 0.38 only |
| brand match with a view | 0.94 | no | 0.97 | no |
| co-view neighbour of a view | 1.37 | no | 1.22 | yes |
| price cut | 0.73 | no | 0.84 | no |
| new product | 1.28 | yes | 1.49 | no |
| new shopper | 0.89 (1.31 / 0.68) | no | 2.76 | no |
| home page / category page | 0.89 / 0.97 | no / yes | 0.77 / 1.03 | no |
| in views × category page | 1.28 | yes | 1.15 | yes |
| clicked through our list earlier today, not bought (633) | 1.17 | yes | 0.99 (16 clicks) | no |
| bought earlier today (971) | 0.89 | yes | 0.99 (2 clicks) | — |

Click: 21 of 37 indicators are stable. Near round numbers: slot 2–3 ×0.5, slots 7–9 ×0.25, main category ×2,
carted × high cart rate ×2.5, phrase share > 0.38 ×5, first view ×2.5. Log appeal 4.5 per log unit means click
∝ appeal^1.5: rules4's appeal^1 under-weights popularity.

The category-rank multipliers fall below 1 because the baseline ("never viewed this category") mixes in new and unknown
shoppers. They give a ratio, not a factor: top category ×4.4 over "other".

## Held out (newest 20%, purchased product among the 10 shown)

| Model | Click AUC | Buy AUC | Buy given click AUC | First % | Top 3 % |
|---|---|---|---|---|---|
| linear (logit, indicators) | 0.795 | 0.871 | 0.664 | 32.3 | 62.4 |
| ranker2 (LightGBM) | **0.835** | **0.913** | **0.683** | **41.0** | **73.8** |
| rules4 score | 0.710 | 0.734 | 0.569 | 28.8 | 59.8 |
| *diagnostics, top 3 %:* LightGBM on the same indicators | | | | 36.2 | 61.6 |
| logit on indicators + ranker2's 33 features (standardised) | | | | 35.8 | 68.1 |
| linear click × ranker2 buy | | | | 34.5 | 66.4 |
| ranker2 click × linear buy | | | | 41.9 | 73.8 |

## Verdict
- **Rejected as a ranker.** It is 11.4 points behind ranker2 on top 3 (bar: within 2). It beats rules4 by 2.6.
- **The form is not the problem; the inputs are.** Trees on the same 0/1 indicators do no better (61.6). What is lost
  is in the continuous click inputs that ranker2 keeps: phrase share, subcategory, brand and category shares, category
  carts, log views and buys, price, segment, session phrase overlap.
- **The purchase-given-click model is fully log-linear.** Swapping ranker2's buy model for the logit costs nothing
  (73.8). Its biggest factors are stable: appeal^1.1 on the odds, phrase share > 0.38 ×4.6, main category ×1.65,
  not the top category ×0.4–0.5, viewed-never-carted ×0.56.
- About half the factors move more than 25% between halves, so a clean round-number formula is not supported. What
  does hold: the slot curve (≈ 1/log2(k+1) on clicks), main category ×2, and the cart effect, which exists only for
  high-cart shoppers (×2.5) and is nil otherwise (×1.03).
- Our own earlier click shows a click lift of ×1.17 (stable) and no purchase lift: too few rows (16 clicks).

## Next
1. Keep ranker2's click model. Its buy model may be swapped for the 37-coefficient logit if robustness to the final's
   new products matters (no loss offline).
2. rules4/rules5: raise appeal to the power 1.5 for clicks; make the cart bonus conditional on cart rate ≥ 0.08.
3. Feed `log_appeal`, the phrase buckets and `carted × high cart` to ranker2 as features (cheap; trees cannot invent the product).
4. Re-run `uv run python eda/linear/fit.py` after the Sunday practice, for a third time split.
