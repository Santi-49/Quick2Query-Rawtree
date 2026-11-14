# H-blend · fusing ranker2 and rules5

- **Status:** live trial since 14 Nov 21:38 UTC
- **Owner:** main session
- **Claim:** the two strategies fail on different requests (rules5 ranks today's carts first 68% of the time, ranker2 33%; ranker2 wins everywhere else), so a rank fusion of their lists beats both.
- **Test:** `blend1` = reciprocal rank fusion of the two top-10 lists (weights 1.0 / 0.6, K 10). Replay held out in time, 574 purchases, `eda/replay/holdout3.py`.
- **Result (blend1 vs ranker2):** ordinary top 1 32.7 vs 34.9, top 3 59.2 vs 59.5, top 10 88.8 vs 85.4. New shoppers top 1 39.1 vs 36.0, top 3 67.6 vs 65.3, top 10 89.3 vs 85.3. Today-cart purchases top 1 49 vs 33. Each cell ± about 3.
- **Also checked live, 17:20 to 21:10:** no shopper segment (new or returning, by number of recent views) where rules5 beats ranker2 beyond noise, so routing by segment between the two has nothing to gain. Returning with 1 view 2.46% vs 1.93%, with 4+ views 1.95% vs 1.39%; new shoppers within noise.
- **Verdict:** small edge offline, strongest for new shoppers and in top 10. Worth a live trial.
- **Next:** first in `queue.toml`.
