# H-ml-signals · new signals found by the wide models, re-checked on live feedback
- **status**: confirmed on live feedback (observational: the lists were chosen by our arms, so the products are not random). Not yet in any strategy.
- **owner**: agent
- **claim**: four signals that are not in `docs/SIMULATOR.md` or the 21 ranker features raise live click and purchase rates by ×3–×17, on top of the known session and category effects: (1) phrase taste, (2) phrase overlap with the recent views, (3) carted in history and not bought, (4) organic co-view from the recent views.
- **test**: `eda/ml/gbm.py` (permutation importance on the newest 20% of live requests, 188 features) chose them; `sql/hypotheses/H-ml-signals.sql` re-runs each one in RawTree on `team_01.feedback` (run 14 Nov ~18:00 UTC, 64k requests, ~1,900 clicks, ~600 purchases). Rate = clicks or purchases per 100 impressions weighted 1/log2(slot+1). Details and the other 11 signals: `docs/findings/08-ml-patterns.md`.

## result
**(1) Phrase taste**: products the returning shopper never viewed, by the share of their history views that carry the product's 2 phrases (summed)

| phrase share | imps | clicks | buys | click_pw | buy_pw |
|---|---|---|---|---|---|
| ≤ 0.22 | 145,252 | 80 | 13 | 0.125 | 0.020 |
| 0.22–0.30 | 98,203 | 164 | 34 | 0.369 | 0.076 |
| 0.30–0.38 | 39,479 | 160 | 37 | 0.889 | 0.205 |
| > 0.38 | 14,449 | 141 | 63 | **2.114** | **0.944** |

It holds inside each category-share bucket and each subcategory-share bucket (eda tables, live and history). It is the largest single feature in both the live click and buy models.

**(2) Phrase overlap with the recent views** (shown product not in the views), click_pw by number of phrase matches 0 / 1 / 2 / 3+:
same subcategory as the last view 0.77 / 1.83 / 1.71 / 4.62 (71 / 98 / 26 / 19 clicks); same category 0.81 / 1.51 / 1.66 / 2.12 (225 / 261 / 83 / 30); other category 0.27 / 0.65 / 0.77 / 1.30 (241 / 377 / 141 / 74). Buys follow: other category 0.043 → 0.49.

**(3) Carted in history, not bought**, click_pw / buy_pw (clicks):

| page | never | viewed only | carted once | carted 2+ | bought |
|---|---|---|---|---|---|
| product | 0.42 / 0.13 (323) | 0.57 / 0.08 (187) | 2.18 / 0.79 (185) | 3.92 / 1.19 (86) | 0.19 / 0.05 (12) |
| category | 0.51 / 0.12 (171) | 0.54 / 0.09 (74) | 2.55 / 1.14 (92) | 3.77 / 1.22 (34) | 0.15 / 0 (4) |
| home | 0.21 / 0.017 (50) | 0.35 / 0.028 (50) | 1.53 / 0.26 (58) | 3.27 / 0.84 (31) | 0 / 0 (0) |

The effect is largest for shoppers who often cart (strongest interaction found, H² 0.17).

**(4) Organic co-view**, click_pw / buy_pw by co-view count 0 / 1–4 / 5–20 / 21+: same category as the last view 0.55 / 0.93 / 1.46 / 2.40 and 0.15 / 0.30 / 0.55 / 1.20; other category 0.31 / 0.42 / 0.73 / 1.38. Inside the same subcategory nearly every product has 21+ co-views, so it cannot separate products there.

## verdict
Confirmed, all four, with ≥ 30 clicks in the top cell of each. (1) and (3) need a known shopper, (4) a known product, (2) needs neither. Wide LightGBM: live click AUC 0.821 against 0.777 for the 21 ranker features; live purchase AUC 0.909 against 0.872.

## next
- Add `phrase_share`, `session_phrase_overlap`, `carted_not_bought`, `coview`, `shopper_cart_rate`, `cat_carts`, `brand_share`/`sub_share` to the ranker (definitions in 08, last section), retrain, compare in a leaderboard block.
- Candidates: add non-viewed products matching the shopper's top phrases, and history-carted products, to the candidate set, especially on home.
- Re-run the SQL after the final's first hour: new shoppers have no history, so only (2) applies to them; new products lack co-views, so (2) also replaces (4) for them.
