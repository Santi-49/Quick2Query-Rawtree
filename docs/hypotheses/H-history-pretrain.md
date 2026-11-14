# H-history-pretrain · train ranker2 on the history carousel log plus live feedback
- **status**: rejected for the build rule (top 3). Pooling history helps the purchase model and the share ranked first, not the top 3. Nothing built.
- **owner**: agent
- **claim**: adding the history carousel log (66,955 requests, 4–14 Nov) to our live feedback makes ranker2 put the purchased product higher than live feedback alone.
- **test**: `eda/ml/history_plus_live.py`, run 14 Nov, on the cached study tables (`data/ml/table_hist.parquet`, `table_live.parquet`; live = 09:00–16:02, 64k requests). Raw output: `data/ml/history_plus_live_out.txt`.
  - Features: the 21 ranker features plus the closest columns to 8 of ranker2's 13 extras (phrase share, session phrase overlap capped at 4, carts of a not-bought product capped at 3, log co-view, session cart rate, log category carts, brand share, subcategory share). `is_first_view`, `is_later_view`, `in_main_cat`, `viewed_today`, `sub_viewed_today` are not in the tables (history has no "today").
  - Non-transferring effects removed: rows where the shopper bought the product in history are dropped from both tables (as train2 does), so "bought before" is gone; repeat-buy rate, per-shopper purchase counts and carousel CTR are not used. This leaves history 1,455 clicks / 399 purchases (from 2,573 / 1,030: most history clicks were repeat buys).
  - Split: newest 20% of live requests held out (521 clicks, 169 purchases); the rest of live (1,358 clicks) for fitting. train2's LightGBM settings: 300 rounds, `fit_buy` (small model under 1,500 clicked rows). 3 seeds; ± = half the min–max range.
  - Ranking metric: score = P(click at slot 1) × P(buy | click); among the **169** held-out requests with a purchase, share where the purchased product is first / in the top 3 of the 10 shown. One request = 0.6 points.
  - MLP: 64-32, sign-log standardised inputs, NaN flags, one-hot page/device; click and buy nets, early stopping on live 70–80% (so it fits on 70% of live, not 80%). One attempt.

## result
| variant | click AUC | buy given click AUC | purchased ranked 1st % | in top 3 % |
|---|---|---|---|---|
| LightGBM (a) live only | 0.831 ± 0.001 | 0.730 ± 0.002 | 42.0 ± 1.8 | 71.4 ± 2.1 |
| LightGBM (b) pooled + `is_live` | **0.836** ± 0.001 | **0.770** ± 0.000 | **46.2** ± 0.6 | 72.2 ± 0.6 |
| LightGBM (c) pooled, history weight 0.25 | 0.834 ± 0.000 | 0.749 ± 0.001 | 44.8 ± 0.9 | 70.8 ± 1.5 |
| LightGBM (d) fit on history, keep boosting on live | 0.830 ± 0.001 | 0.753 ± 0.002 | 42.4 ± 1.2 | 70.2 ± 0.9 |
| LightGBM (e) history only | 0.814 ± 0.002 | 0.553 ± 0.002 | 40.6 ± 0.3 | 64.7 ± 2.4 |
| MLP (a) live only | 0.832 ± 0.002 | 0.715 ± 0.009 | 38.1 ± 2.1 | 67.9 ± 1.5 |
| MLP (c) history weight 0.25 | 0.832 ± 0.001 | 0.738 ± 0.025 | 37.3 ± 2.4 | 68.0 ± 0.9 |

## verdict
- **Top 3: no difference.** Best variant (b) is +0.8 points over live only, inside the seed spread (±2.1), and 0.8 points is about one request out of 169.
- Pooling with `is_live` helps the purchase-given-click model (0.770 against 0.730 AUC, outside the spread) and the share ranked first (+4.2 points, 7 requests; outside the seed spread, but seeds do not measure the sampling noise of 169 requests, whose binomial standard error is ~3.8 points). Click AUC +0.005.
- Weighting history 0.25 or continued boosting gives less than pooling with a flag. History alone is worse everywhere; its purchase model is near chance (0.553) once "bought before" is removed.
- The MLP agrees: history adds to its purchase net (0.715 → 0.738, noisy) and nothing to the ranking. It is below LightGBM on the ranking.
- The live table is from 16:02; production train2 now fits on more live feedback, which shrinks whatever history adds.

## next
- Not built: `train2.py` is unchanged. If tried later, the variant to try is (b), pooled with an `is_live` flag (set to 1 when serving), not a weight: it changes the feature list, so it cannot sit behind a weight-only switch without changing the model format.
- Re-run on the current live table (`build.py refresh`) when there are 2× the held-out purchases; a top-1 gain that holds then would justify a leaderboard block.
