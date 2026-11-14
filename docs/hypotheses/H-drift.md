# H-drift · the simulator's parameters move over time

- **Status:** rejected, except for the known trend bursts. No change to training.
- **Owner:** agent, 14 Nov evening (Santi's hypothesis, `strategies.toml` QUEUED 2)
- **Code:** `eda/drift/counts.py` (tests 1, 2), `eda/drift/blocks.py` (test 3), `eda/drift/fresh.py` (tests 4, 5),
  `sql/hypotheses/H-drift.sql`. `train2.fit_buy` gained an optional `w` (sample weights); the default is unchanged.
  Outputs: `data/drift/*_out.txt`, `data/drift/fresh_A2.txt`, `fresh_B2.txt`. Models go to `data/drift/models/`, never `models/`.

## Claim
Things we treat as fixed (per-product buy propensity, subcategory, brand and phrase appeal, a hidden trend vector) drift
during the day. If so, recent feedback should get more weight, or ranker2 should be trained on a short window.

## Test
1. Live organic events 09:00–21:00 UTC: purchases per view per product (1,016 with at least 30 buys) per 2-hour and
   1-hour block. Chi2 of the observed buys against a product rate × global block factor, divided by its df. The noise
   floor is the same statistic between two random halves of shoppers inside one block, so shopper clustering is
   included. Group residuals summed by subcategory, brand, phrase and category: co-movement shows as a group ratio
   above its within-block floor. `tau` is the excess coefficient of variation of the true rate across blocks.
2. The same on the history (16 Sep–13 Nov, 59 days, 2,373 products), plus lag 1–7 autocorrelation of the residuals
   and the share of the first 3 principal components of the subcategory × day residual matrix, against a day-shuffled null.
3. The H-loglinear logits (`eda/linear/fit.py` rows and indicators) refitted per 2-hour block. Per indicator:
   Cochran's Q across blocks and the slope z on block index.
4. Leak-free replay (`q2q.replay`, State rebuilt per request, `state.trend` emptied in every variant). ranker2 is
   trained on all feedback before the cut, on only the last 1, 2 or 4 h, or on all of it with half-lives of 1, 2 or 6 h,
   and scored on the 3 h after the cut. There are two windows: A 18:15–21:15 (565 purchases) and B 15:15–18:15 (465).
5. The same machinery, with the training cut 0, 20, 60 or 180 minutes before the window. **Noise reference:** the `all`
   model refitted with two other LightGBM seeds (`seed2`, `seed3`). Natural experiment: the live model was frozen at
   its 19:34 version from 19:47 to 20:57 UTC (statement 3 of the SQL).

## Result

**1. Live, today.** Products: between-block chi2/df 1.10 against a within-block floor of 1.01 (2 h). With 1 h blocks it
is 1.05 against 1.00. The global buys/view factor stays within ±1% in every block. The excess is all in subcategories:
subcategory 2.17 against 1.12, category 2.92 against 1.06, brand 1.31 against 0.96, phrase 0.94 against 1.32 (none).
It comes from five subcategories, one after another, each lifted for about 2 hours: Aquariums 09–11, Kettles 11–13,
Cutting Boards 13–14, Bike Helmets 15–16 and Game Consoles 19–21. Views rose ×1.6–2.3 and buys per view ×1.3–1.8 at
the same time. The correlation of the subcategory buys/view residual with the log view lift is +0.58. **With those
five subcategories left out**, products show 1.03 against 1.01 (tau 1.2%), subcategories 1.17 against 1.10 (tau 0) and
brands 1.07 against 0.93. Today against the 60-day history, on 972 products outside the bursts: global ratio 1.000,
chi2/df 1.055, correlation of log buys/view 0.959.

**2. History, daily.** Products: 1.002 against a floor of 1.009, tau 0. Subcategory 1.02 against 1.06, brand 0.98 against
1.05, category 0.88 against 1.14. Weekly units give the same. Lag 1–7 autocorrelation, subcategories: −0.042, −0.012,
−0.016, −0.019, −0.012, 0.000, −0.015. The bias from zero-sum residuals is −0.017 and the se 0.014, so it is zero at every
lag: no random walk, no smooth trend. The first 3 principal components hold 15.7%, against 15.3% in the shuffled null
(95th percentile 15.9%). View-share chi2/df is 3.2, against 44 live: the history has no trend bursts.

**3. Multipliers per 2-hour block.** Purchase given click: none of 37 indicators is flagged (Q p < 0.01 or |slope z| > 3).
Click: 9 are flagged, including log appeal 5.4 → 1.9 from 13h to 19h (z −4.1), main category 2.4 → 1.5 (z −4.2), top
category, phrase share > 0.38, co-view and new shopper (the last three are high only in 09–13h). The organic events
in tests 1 and 2 show no such movement, and the mix of arms that chose the shown lists changed through the day
(rules → ranker2), which changes the candidates each logit sees. So these click shifts are most likely
selection by the logging policy, not simulator drift. The purchase decision, which no policy touches, is stable.

**4 and 5. Replay.** Paired variant − `all`, hit3 averaged over routes weighted by request share (points ± bootstrap se).
Levels for `all`: window A main hit3 61.5, new 65.5; window B 51.9, 54.0. Per-route hit1, hit3 and hit10 are in
`data/drift/fresh_A2.txt` and `fresh_B2.txt`.

| variant | window A | window B |
|---|---|---|
| seed2 (noise) | −5.0 ± 1.6 | −0.2 ± 1.3 |
| seed3 (noise) | −2.7 ± 1.6 | −1.0 ± 1.5 |
| cut20 | −2.5 ± 1.5 | +0.6 ± 1.4 |
| cut60 | −4.8 ± 1.6 | +0.2 ± 2.0 |
| cut180 | −10.9 ± 2.2 | −22.9 ± 2.9 |
| last4h | −4.0 ± 1.7 | −3.6 ± 1.9 |
| last2h | −9.2 ± 1.9 | −2.6 ± 1.8 |
| last1h | −14.8 ± 2.4 | −17.7 ± 2.9 |
| hl6h | −3.0 ± 1.3 | +1.4 ± 1.5 |
| hl2h | −4.9 ± 1.6 | −0.2 ± 1.7 |
| hl1h | −6.5 ± 1.8 | −5.7 ± 2.1 |

**Changing only the seed moves hit3 by up to 5 points**, more than the bootstrap se, which treats the model as fixed.
Against the mean of the three seed fits (A −2.6, B −0.4), averaged over both windows: cut20 +0.5, cut60 −0.8,
hl6h +0.7, hl2h −1.0, last4h −2.3, last2h −4.4, hl1h −4.6, last1h −14.8 and cut180 −15. Counting both bootstrap and seed
noise, the se of each of these averages is about 1.7. The cut180 loss mixes staleness with less data: in window B
that model saw 161 purchases.

Natural experiment, live conversion per request, ranker2 (shale, shale-n), with rules5 (garnet, garnet-n) as control:

| | 17:47–19:47 | frozen 19:47–20:57 | after 20:57 |
|---|---|---|---|
| ranker2 | 2.04 ± 0.16% (7,344) | 2.39 ± 0.22% (4,901) | 2.48 ± 0.31% (2,462) |
| rules5 | 1.98 ± 0.16% (7,592) | 2.00 ± 0.20% (5,052) | 1.52 ± 0.38% (1,055) |

Frozen against before, difference in differences: +0.33 ± 0.37 points. The freeze did not hurt.

## Verdict
- **No drift in the static parameters.** Per-product buy propensity sits at the binomial floor in the history (59 days)
  and today, and today's rates equal the history's. Brand and phrase appeal do not move. Nothing has autocorrelation
  or a common factor.
- **The one moving part is the trend schedule.** One subcategory at a time, for about 2 hours, gets ×2 views and ×1.3–1.8
  buys per view. It is a step, not a random walk. ranker2 already multiplies by `state.trend` (15 min against 120 min
  of views). The new fact is that the trend also lifts buys per view, not only views.
- **Recency weighting or a short window: no.** A half-life of 6 h ties (+0.7 ± 1.7). Every shorter window or
  half-life loses, from −2.3 (last 4 h) to −14.8 (last hour). With about 1,500 purchases in all, ranker2 needs the
  volume more than freshness.
- **Retraining more often than every 20 minutes: no.** A model 20 minutes older ties (+0.5 ± 1.7) and so does one 60
  minutes older (−0.8 ± 1.7). Live, the 70-minute freeze cost nothing (+0.33 ± 0.37). Only a 3-hour gap loses, and
  that is mostly lost data.

## Next
1. Keep `train2` as it is: all feedback, unweighted, every 20 min or slower. On the VM (QUEUED 3) a 60-minute
   cadence costs nothing measurable.
2. Check that `state.trend` reacts within the first 15–30 minutes of a burst and that its size matches ×1.3–1.8 on buys
   as well as views. During the final, trends are the only thing that moves.
3. Any offline comparison of two ranker models must include seed refits: one refit swings hit3 by up to 5 points.
