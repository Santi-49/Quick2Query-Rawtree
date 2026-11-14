# 10 · Offline replay (`q2q replay`)

Scores any strategy on our logged requests in one to two minutes instead of a 30-minute live window. It replays logged outcomes; it does not simulate shoppers. Code: `src/q2q/replay.py`, `eda/replay/pull.py`, `eda/replay/holdout.py`.

## Run

```
uv run q2q replay rules4 ranker2 cold2 --hours 4     # names default to the seven below
uv run q2q replay rules5 --hours 4 --refresh         # pull the window again (about 10 s), else the cache in data/replay/
uv run eda/replay/holdout.py 2                       # ranker, ranker2 retrained on feedback before the window, then replayed
```

The State loads as in the router (12–30 s, read-only). Live purchases, today's views and every cart are rebuilt for each request from what happened before it. Each strategy answers through `guard()`. It replays every request with a purchase, up to 2,500 requests followed by an organic purchase (`--organic`) and 1,000 uniform requests (`--sample`), about 4,000 requests. Per strategy: rules4 8 s, cold2 9 s, ranker2 45 s. The command above takes 110 s end to end, pull included. The validation below used 4,000 / 2,000; its windows differ slightly run to run because trend and catalogue are read at run time.

## Metrics

Per route (main, new_shopper, no_views) and `all` (routes weighted by their share of requests: 56 / 24 / 20%), each with a bootstrap standard error.

| Metric | On | Meaning |
|---|---|---|
| `hit1`, `hit3`, `hit10` | requests where a shown product was purchased | that product is in the strategy's top k |
| `hit10_other` | the same, logged by another arm (fallback counts as baseline) | `hit10` without the logging arm's own advantage |
| `organic10` | requests followed within 30 min by an organic purchase of a product we did not show | one of those products is in the top 10 |
| `overlap` | uniform sample | share of the top 10 that was in the logged list |

explore-IPS is not computed. The explore arm logs the propensity of the stratum it drew, not the marginal probability of a product across overlapping strata. A deterministic top 10 almost never matches its random slots. And it had 2 purchases in 1,331 requests.

## Validation

Live conversion, ordinary requests: ranker2 2.0 > rules4 1.8 > rules2 1.25 ≈ ranker 1.15 (> baseline 0.65). Home: cold2 0.6 > rules2 0.4 ≈ cold1 0.35.

Main route, window 15:41–17:41 UTC (183 purchases, 1,013 organic). "Holdout" = ranker models fitted on feedback before 15:41. "In-sample" = the production models, fitted on feedback that includes the window.

| Strategy | hit1 | hit10_other | organic10 | hit1 in-sample | hit10_other in-sample |
|---|---|---|---|---|---|
| ranker2 | 29.0 ± 3.2 | **80.8 ± 3.1** | 6.3 ± 0.7 | 56.8 | 91.4 |
| rules4 | 29.5 ± 3.1 | **76.6 ± 3.6** | 4.8 ± 0.7 | | |
| rules2 | 23.0 ± 3.1 | **62.3 ± 4.2** | 1.7 ± 0.4 | | |
| ranker | 21.3 ± 2.8 | **60.6 ± 3.9** | 2.3 ± 0.5 | 30.1 | 77.5 |

Window 13:37–17:37 UTC (4 h, production models), `hit10_other` main / `organic10` no_views: baseline 21.9 / 4.5, rules2 74.9 / 1.8, rules4 82.2 / 4.3, ranker 81.2 / 4.5, ranker2 92.0 / 7.3, cold1 63.9 / 2.4, cold2 61.3 / 4.7.

- **`hit10_other` on the main route, with models fitted before the window, orders the four ordinary arms exactly as live**, and puts baseline far last. It is the filter.
- `hit1` agrees with live except that it cannot separate rules4 from ranker2 (live gap 0.2 points).
- **Models scored in-sample are inflated**: on the 4 h window ranker2's `hit1` is 55.6 and ranker climbs above rules2. Always use `holdout.py` (or a window after the model's training time) for a model strategy.
- `organic10` on home puts cold2 first, as live, but rules2 and cold1 swap (live gap 0.05 points, within noise). It also rates baseline (4.5) level with cold2 and rates baseline above rules4 on main (5.9 against 4.5): it rewards popularity. Use it only to compare home strategies with each other, never against the best-seller list.
- ranker2 has the highest `organic10` on home (7.3, holdout 7.5, 305 requests). A candidate for the home route, to be tried live.

## Caveats

- Hit@k only sees products we showed. A strategy that finds good products nobody showed is not credited except by `organic10`.
- Differences under 2 standard errors decide nothing; the arms are scored on the same requests, so a paired comparison would be tighter.
- State as of now: catalogue, appeal, trend, price cuts, segments, co-views. Stock is ignored (every active product counts as available). Products created during the window may be recommended before they existed.
- Feedback has no cart outcome, only click and purchase.
- Organic purchases follow popularity more than the session: 0.7% of them are a product in the request's recent views, 32% are in the last view's category. The organic log was generated without the no-rebuy rule, so some organic purchases are products a strategy correctly excludes.
- The last 30 minutes of the window have no organic metric (the 30-minute window is incomplete).
- Hand-set weights (rules4, cold2) were tuned on live feedback that overlaps the window: mildly in-sample too.
