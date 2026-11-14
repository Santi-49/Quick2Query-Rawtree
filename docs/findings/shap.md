# SHAP: what drives ranker2, and does it move between retrainings

Script: `eda/shap/shap.py` (LightGBM `pred_contrib=True`, one thread). Raw output: `data/shap/report.txt`.
Fixed sample (`data/shap/sample.npz`, from `data/drift/table.npz`, rows up to 21:22 UTC): click model on 20,000 random impressions, buy model on all 4,873 clicked impressions.
Share = mean |SHAP| of the feature / sum over features, in %. SHAP is in log-odds.

Snapshots (same sample, same features, 300 trees each):
- `cut 15:15z`, `cut 17:15z`, `cut 18:15z`: drift-test models fitted on every row before that UTC time (`data/drift/models/`).
- `live 22:18`: the live model as it was at 22:18 UTC (file written 22:06).
- `live 22:34`: the next retraining (file written 22:34). Only these two live snapshots exist: the model did not change between 22:06 and 22:34, so two retrainings fell inside the window, not three.
Note: the sample is partly inside the training data of the later models, so shares are importance, not out-of-sample skill.

## Click model (top 16 of 34 features, ordered by the latest snapshot)

| feature | 15:15z | 17:15z | 18:15z | live 22:18 | live 22:34 | change 22:34 vs 15:15z | direction (corr, SHAP lowest / highest quintile) |
|---|---|---|---|---|---|---|---|
| phrase_share | 16.25 | 17.16 | 16.78 | 16.14 | 16.33 | +0.08 | up: r +0.95, -0.98 / +0.69 |
| slot | 8.66 | 10.00 | 10.68 | 12.61 | 12.46 | +3.80 | down (worse slot, lower): r -0.91, +0.56 / -0.34 |
| shopper_cart_rate | 8.44 | 8.97 | 9.86 | 11.20 | 11.35 | +2.92 | up: r +0.94, -0.56 / +0.66 |
| session_phrase_overlap | 8.26 | 8.63 | 8.32 | 8.27 | 7.70 | -0.56 | up: r +0.95, -0.19 / +0.23 |
| cat_share | 7.16 | 6.35 | 6.10 | 6.82 | 7.19 | +0.03 | up: r +0.91, -0.17 / +0.35 |
| cat_carts | 6.34 | 5.96 | 5.77 | 5.78 | 5.52 | -0.82 | up: r +0.75, -0.33 / +0.11 |
| appeal | 3.87 | 5.24 | 4.82 | 4.58 | 4.51 | +0.64 | up: r +0.76, -0.28 / +0.13 |
| sub_share | 5.02 | 4.54 | 4.42 | 3.41 | 4.22 | -0.80 | up: r +0.77, -0.25 / +0.16 |
| coview | 3.95 | 3.79 | 3.60 | 4.30 | 4.08 | +0.13 | |
| sub_viewed_today | 2.84 | 3.44 | 3.94 | 3.86 | 4.03 | +1.18 | |
| brand_share | 4.79 | 4.70 | 3.89 | 3.66 | 3.00 | -1.79 | |
| in_main_cat | 2.71 | 3.76 | 3.70 | 2.51 | 2.97 | +0.26 | |
| n_views | 3.66 | 2.66 | 2.25 | 3.43 | 2.89 | -0.76 | |
| carted_not_bought | 2.17 | 2.34 | 2.36 | 2.35 | 2.39 | +0.22 | |
| same_cat_last | 1.00 | 1.33 | 1.40 | 2.03 | 2.10 | +1.10 | |
| log_views | 4.77 | 2.93 | 2.96 | 1.36 | 1.62 | -3.16 | |

Remaining features are under 1.6% each; `known_shopper`, `new_shopper` are 0.00, `is_new_product`, `is_first_view`, `is_later_view`, `is_last_view`, `same_sub_any`, `viewed_before`, `device`, `viewed_today`, `views_ago` are 0.2% or less.

## Buy-given-click model (top 16 of 34 features)

| feature | 15:15z | 17:15z | 18:15z | live 22:18 | live 22:34 | change 22:34 vs 15:15z | direction (corr, SHAP lowest / highest quintile) |
|---|---|---|---|---|---|---|---|
| shopper_cart_rate | 18.12 | 16.27 | 16.80 | 18.80 | 18.31 | +0.18 | up: r +0.96, -0.89 / +0.88 |
| appeal | 5.37 | 9.88 | 9.64 | 7.16 | 8.40 | +3.03 | up: r +0.94, -0.37 / +0.32 |
| phrase_share | 13.03 | 8.71 | 7.84 | 7.57 | 7.80 | -5.23 | up: r +0.90, -0.53 / +0.43 |
| session_phrase_overlap | 5.91 | 7.91 | 6.37 | 7.52 | 6.51 | +0.60 | up: r +0.83, -0.25 / +0.21 |
| cat_share | 6.82 | 8.60 | 7.60 | 4.11 | 5.18 | -1.64 | up: r +0.72, -0.12 / +0.16 |
| same_cat_any | 5.70 | 5.84 | 5.56 | 4.67 | 4.67 | -1.03 | up: r +0.97, -0.18 / +0.11 |
| segment | 5.05 | 3.58 | 4.07 | 4.11 | 4.05 | -0.99 | up: r +0.66 (a code), -0.07 / +0.16 |
| n_views | 4.70 | 4.06 | 3.99 | 4.03 | 3.95 | -0.75 | down: r -0.84, +0.12 / -0.19 |
| in_views | 5.47 | 2.91 | 3.07 | 3.90 | 3.72 | -1.75 | |
| coview | 5.72 | 2.57 | 2.62 | 3.13 | 3.64 | -2.08 | |
| sub_share | 1.99 | 3.03 | 3.32 | 3.11 | 3.57 | +1.58 | |
| brand_share | 4.60 | 3.00 | 3.26 | 3.41 | 3.42 | -1.17 | |
| carted_not_bought | 0.00 | 2.64 | 3.83 | 3.83 | 3.35 | +3.35 | |
| log_buys | 1.35 | 1.08 | 1.62 | 4.08 | 2.94 | +1.59 | |
| in_main_cat | 1.44 | 1.45 | 3.69 | 2.93 | 2.92 | +1.48 | |
| log_views | 4.78 | 3.37 | 3.25 | 2.95 | 2.89 | -1.89 | |

## Noise floor

- Sampling noise (5 bootstrap resamples of the evaluation rows, latest snapshot): sd of a share is at most 0.05 pts for the click model and 0.12 for the buy model (mean 0.01 and 0.03). Negligible.
- Refit noise (same data and cut, three seeds, `all`, `seed2`, `seed3`, in each of the two drift windows, sd averaged over the windows): mean 0.11 pts for the click model (largest: shopper_cart_rate 0.37, phrase_share 0.32, cat_carts 0.27, appeal 0.27), mean 0.18 for the buy model (largest: shopper_cart_rate 0.52, appeal 0.46, phrase_share 0.45, same_cat_any 0.43, same_cat_last 0.43, log_views 0.41). Only two windows with three fits each, so these sds are rough. A move under about 1 pt on a feature is within about 2 to 3 refit sd for the big features and should not be read as a change; the buy model, trained on about 5,000 clicked rows, is the noisier of the two. This is importance noise from the seed only, it does not cover the different training data between snapshots.

## Reading

- The click model is driven by phrase_share (16%), slot (12.5%), shopper_cart_rate (11%), session_phrase_overlap (8%), cat_share (7%), cat_carts (5.5%). These six carry about 60% of the total. Everything else is below 5%.
- The buy model is dominated by shopper_cart_rate (18%), then appeal (8%), phrase_share (8%), session_phrase_overlap (6.5%) and cat_share (5%).
- Directions are what the names say: more phrase match, category/sub-category share, cart rate, appeal go up with the score. `slot` goes down (slot 1 is worth about +0.56 log-odds against the later slots), `n_views` goes down for purchase.
- Importance is not constant, but the top of the ranking is. Between consecutive live retrainings (22:18 to 22:34, 16 minutes apart) the largest move is 0.80 pts (click, sub_share) and 1.24 pts (buy, appeal); 3.0 and 4.4 pts of share changed hands in total. Those are about 2 to 3 refit sd for the largest single moves, so a little beyond seed noise but small, and part of it is new data.
- Beyond noise, over the longer span (cut 15:15 to now): click slot +3.8 and shopper_cart_rate +2.9 (both rising steadily across all five snapshots) and log_views -3.2; buy phrase_share fell from 13% to 8% between the 15:15 and 17:15 cuts and stayed there, appeal rose from 5% to 8 to 10%, carted_not_bought went from 0 to 3.4%. These are 5 to 10 times the refit sd, so real changes in what the model learned as feedback accumulated (the 15:15 model saw far fewer clicks).
- Surprises: `known_shopper` and `new_shopper` have exactly zero importance in both models (constant in the training rows, or fully carried by shopper_cart_rate). `is_new_product`, the first/later/last-view flags and `device` are near zero. `phrase_share` is the strongest click feature, ahead of `slot`, and `log_views` (once 4.8% of the click model) has almost vanished.
- No feature has a direction opposite to its name. `segment` is a categorical code treated as a number, so its correlation (+0.66) is not meaningful.
- Caveats: the sample is partly in-sample for the live models; the click sample has only 81 clicks in 20,000 rows, which is fine for SHAP shares but thin for the quintile means of rare features; direction columns use the latest snapshot.
