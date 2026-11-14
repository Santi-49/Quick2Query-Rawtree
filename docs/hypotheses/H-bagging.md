# H-bagging · ranker2 with averaged, regularised boosters (ranker6)
- **status**: rejected offline (mixed, and 6x over the compute budget); `ranker6` not promoted.
- **owner**: agent, 14 Nov night
- **code**: `src/q2q/train6.py`, `src/q2q/strategies/ranker6.py`, `eda/replay/holdout67.py`, `eda/replay/timing67.py`, `tests/test_ranker6.py`

## Claim
ranker2's purchase-given-click model is fitted on about 1,000 purchases and is noisy (held-out AUC about 0.69).
Averaging 5 boosters with row and feature subsampling (0.8 / 0.8), with or without stronger regularisation, lowers
the variance and ranks the purchased product higher.

## Test
Same rows and features as train2. Configurations, each model separately:
click `r2` (ranker2: 300 rounds), `bag5` (5 seeds, bagging 0.8, features 0.8), `reg_bag5` (lr 0.02, 7 leaves,
min 400 per leaf, early stopping); buy `r2` (train2's rule), `bag5`, `reg_bag5` (lr 0.02, 4 leaves, min 60, L2 20,
early stopping), `reg2_bag5` (3 leaves, min 120, L2 50). Chosen **inside the training rows**: three expanding time
folds (fit on the oldest 55 / 70 / 85% of impressions, score the next 15%; early stopping on the newest 15% of each
fold's fit rows). Best mean click AUC and best mean buy AUC win; refitted on every row (median best round).
Then the holdout3 method: every model fitted on data before 18:28:32 UTC, replayed on 18:28–21:28 UTC
(574 purchases, 2,500 organic, 3,915 requests), paired against ranker2 refitted on the same rows.

## Result
Selection folds (3,101 clicks, 964 purchases before the cut):

| config | click AUC (mean of 3 folds) | buy AUC (mean) |
|---|---|---|
| r2 | 0.831 | 0.709 |
| bag5 | 0.832 | 0.714 |
| reg_bag5 | 0.832 | 0.711 |
| reg2_bag5 | | 0.716 |

Chosen: click `bag5`, buy `reg2_bag5` (about 830 rounds). Purchased product first / top 3 over the folds (540
requests): r2 x r2 41.7 / 70.1%, bag5 x reg2_bag5 42.0 / 71.1%, best pair bag5 x bag5 42.7 / 72.4%. All within noise.

Paired ranker6 − ranker2, same requests (points, ± bootstrap se, n):

| route | hit1 | hit3 | hit10 | hit10 on requests not logged by ranker2 |
|---|---|---|---|---|
| main | **+4.7 ± 2.0** (321) | +1.6 ± 2.0 | −1.6 ± 1.3 | +0.0 ± 1.9 (131) |
| new_shopper | −1.8 ± 2.1 (225) | **−4.0 ± 2.0** | −0.9 ± 1.1 | +2.0 ± 1.5 (100) |
| no_views organic10 | +0.4 ± 0.5 (471) | | | |

Compute in the replay (laptop, through guard): ranker2 48 s, ranker6 299 s for 3,915 requests: **12 ms against
76 ms per request**. Ten booster calls (5 click x 300 rounds, 5 buy x ~830 rounds) instead of two.

## Verdict
- Mixed: better hit1 on main (+4.7, two se), worse hit3 on new shoppers (−4.0, two se), the rest ties. With nine
  paired lines, two at two se in opposite directions is what noise gives. **Tie.**
- The validation folds agree: bagging moves AUC by 0.001–0.007, inside fold-to-fold spread (0.03).
- 76 ms per request on the laptop breaks the 15 ms budget (prod is 1 vCPU). Not promotable even if it won.

## Next
- If retried: bag only the buy model with 3 boosters of ~100 rounds (compute ~2x ranker2), on a window after more
  purchases have accumulated. The variance of the buy model is not the bottleneck at today's volume.
