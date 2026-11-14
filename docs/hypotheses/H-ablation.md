# H-ablation · which pieces of ranker3 and rules5 are real, and ranker8 built from them
- **status**: ranker8 ties ranker2 and blend1 on held-out time, with clear upside on today-cart purchases; candidate for a live trial, not promoted.
- **owner**: agent, 14 Nov night
- **code**: `eda/replay/ablation8.py`, `eda/replay/test8.py`, `src/q2q/train8.py`, `src/q2q/strategies/ranker8.py`, `tests/test_ranker8.py`

## Claim
Some of ranker3's 44 inputs and rules5's hand constants are noise or harmful at about 1,000 purchases. Dropping
them, and giving the trees rules5's rank as one input, makes a model that generalises better than ranker2.

## Test
One training table with every input of ranker3 plus `rules5_rank` (rules5's position of the shown product, 1–10, else 11,
with the State set to each request's time). 1,257,451 impressions, 5,273 clicks, 1,631 purchases to 21:59 UTC. Every input is
built from data before its request, so a cut is a slice of rows before the window.

- **Ablation, 3 cuts**: replay windows 13–15, 15–17, 17–19 UTC (205 + 289 + 329 = 823 purchase requests), models fitted on rows
  before each window. Click models on every click plus 30% of the other impressions (weight 1/0.3; same rows for every variant
  of a cut), buy-given-click models on every click, train2's parameters. One group dropped at a time from both models. Paired
  differences against the full model (ranker3's inputs) on the same requests, pooled over the cuts, bootstrap se. State as of each
  request, including cart times and our earlier clicks (as holdout3).
- **rules5**: one constant set to neutral at a time by monkeypatching, same 823 requests.
- **Selection** (same 3 cuts, all rows): ranker8's set with train2's and with train8's parameters against ranker3's inputs + rules5_rank.
- **Test**: window 19:00–22:00 UTC (579 purchase requests), not used for any choice. ranker2 (its 34 columns, train2's parameters)
  and ranker8 fitted on all 935,130 rows before 19:00. blend1 uses that ranker2. State as prod has it (no cart times, no own clicks).

## Result

### Feature groups (dropped − full, points ± se; 823 requests: main 455, new_shopper 291)

| group | main hit3 | main hit10 | new hit3 | new hit10 | carted today hit3 | verdict |
|---|---|---|---|---|---|---|
| slot | **+5.3 ± 1.8** | **+3.3 ± 1.2** | +2.8 ± 2.3 | +1.2 ± 2.1 | −5.8 ± 3.5 | drop (harmful) |
| product appeal / conversion | −17.4 ± 2.4 | −16.3 ± 2.1 | −20.1 ± 2.9 | −25.7 ± 2.6 | −10.8 ± 5.1 | keep |
| price | −0.4 ± 1.5 | −0.9 ± 1.2 | −0.6 ± 1.3 | +0.9 ± 1.4 | −1.7 ± 2.3 | drop (noise) |
| session relation (recent views) | −10.2 ± 2.0 | −10.0 ± 1.7 | −14.9 ± 2.8 | −19.2 ± 2.9 | −5.0 ± 4.4 | keep |
| session shape | +0.0 ± 1.5 | −1.3 ± 1.3 | +1.5 ± 1.7 | +1.2 ± 1.4 | +1.7 ± 2.7 | drop (noise) |
| shopper history shares | −3.1 ± 2.1 | −2.4 ± 1.7 | −2.2 ± 1.7 | −0.3 ± 1.5 | 0.0 ± 3.6 | keep (main hit1 −4.0 ± 1.8) |
| phrase taste | −11.8 ± 2.2 | −15.4 ± 2.1 | −0.9 ± 1.9 | −1.9 ± 2.1 | −1.7 ± 3.6 | keep |
| history carts, cart rate | −2.7 ± 1.9 | −0.2 ± 1.4 | −1.2 ± 1.6 | −0.3 ± 1.4 | −2.5 ± 3.8 | keep (main hit1 −3.6 ± 1.8, home hit10 −11.8 ± 4.3) |
| co-views | −0.4 ± 1.4 | −0.2 ± 1.2 | **+4.3 ± 1.6** | +2.5 ± 1.5 | +2.5 ± 3.1 | drop (harmful) |
| today's views | −0.9 ± 1.5 | −0.9 ± 1.1 | −0.9 ± 1.4 | +1.2 ± 1.8 | −5.0 ± 2.6 | drop (noise) |
| today's carts | 0.0 ± 1.6 | 0.0 ± 1.3 | −2.2 ± 2.0 | −0.9 ± 1.7 | −15.8 ± 4.1 | keep |
| cart time today (in today's carts) | −0.2 ± 1.4 | 0.0 ± 0.9 | +1.2 ± 1.5 | −0.9 ± 1.0 | +2.5 ± 3.4 | drop (noise; not on the live State) |
| own-list clicks | 0 | 0 | 0 | 0 | 0 | drop (never used by the trees; not on the live State) |
| context (segment, page, device, new) | −0.4 ± 1.5 | +0.2 ± 1.2 | −3.4 ± 1.5 | −0.6 ± 1.3 | −2.5 ± 3.1 | keep |
| **+ rules5_rank** | **+7.6 ± 2.0** | **+4.9 ± 1.5** | **+9.0 ± 2.0** | **+7.7 ± 2.1** | **+15.8 ± 3.9** | add |
| no trend multiplier | +0.4 ± 0.7 | −0.7 ± 0.7 | −0.9 ± 0.8 | 0.0 ± 0.6 | −1.7 ± 1.2 | drop (noise) |
| no price-cut multiplier | 0 | 0 | 0 | 0 | 0 | drop (no cut active in the windows) |
| click only (no buy model) | −2.7 ± 1.6 | −4.0 ± 1.5 | −3.4 ± 1.7 | −1.9 ± 1.1 | +2.5 ± 3.0 | keep click × buy |
| buy only (no click model) | −17.6 ± 2.4 | −17.1 ± 2.3 | −7.7 ± 2.8 | −16.1 ± 3.1 | −33.3 ± 4.8 | keep click × buy |

Full model on these requests: main hit1/3/10 31.4 / 50.6 / 77.3, new 25.4 / 44.3 / 67.5. Fits take 1–2 s each with the subsample.

### rules5 components (neutral − rules5, points ± se, same 823 requests)

| component (neutral value) | main hit3 | main hit10 | new hit3 | new hit10 | carted today hit3 | verdict |
|---|---|---|---|---|---|---|
| today carts ×30 (1) | −0.2 ± 1.7 | −2.7 ± 1.4 | −0.3 ± 2.7 | −7.1 ± 1.9 | −58.3 ± 4.6 | real |
| only view ×18 (first view 12) | −1.6 ± 0.6 | −0.4 ± 0.3 | −1.5 ± 0.8 | 0.0 ± 0.5 | 0 | real, small |
| last view ×3 (other view 5) | 0 | +0.2 ± 0.2 | 0 | +0.6 ± 0.4 | 0 | noise |
| history cart count (1) | −2.0 ± 0.7 | −0.4 ± 0.5 | 0 | 0 | 0 | real, small |
| history cart views (1) | **+3.8 ± 1.2** | +0.7 ± 0.9 | 0 | 0 | 0 | harmful |
| conversion bpv (1) | −7.3 ± 1.7 | −4.5 ± 1.6 | −6.5 ± 2.0 | −4.0 ± 1.8 | 0.0 ± 2.3 | real |
| home flatter cart base (cold2) | home +3.9 ± 3.8 | home +5.9 ± 3.3 | – | – | – | noise (28–60 home purchases) |
| history cart ×6 (1) | −8.2 ± 1.9 | −12.9 ± 1.8 | 0 | 0 | +0.8 ± 0.8 | real |
| session and past ×1.4 (1) | −2.4 ± 1.2 | −3.6 ± 1.1 | 0.0 ± 0.6 | +0.3 ± 0.3 | −1.7 ± 1.2 | real |
| favourite category share (0) | −3.8 ± 1.2 | −6.2 ± 1.4 | 0 | 0 | 0 | real |
| first view ×12 (other 5) | −2.4 ± 0.9 | −2.0 ± 0.7 | −1.9 ± 0.9 | −1.2 ± 1.0 | 0 | real |
| subcategory ×4.5 / 4 (1) | −0.7 ± 1.0 | −4.9 ± 1.2 | −3.4 ± 1.6 | −7.4 ± 1.9 | +0.8 ± 0.8 | real |
| category ×4.5 / 3 (1) | −2.2 ± 1.5 | −8.9 ± 1.8 | −8.4 ± 2.1 | −16.1 ± 2.7 | 0.0 ± 1.6 | real |
| segment (1) | −0.4 ± 0.6 | +1.1 ± 0.7 | −1.2 ± 0.9 | −0.3 ± 1.0 | 0 | noise |
| trend (1) | 0.0 ± 0.9 | +0.9 ± 0.8 | +0.3 ± 0.9 | −0.3 ± 1.0 | +0.8 ± 0.8 | noise |

rules5 on these requests: main 26.7 / 48.8 / 81.3, new 27.2 / 50.2 / 78.6. Its strong parts (today carts, conversion, history carts,
category / subcategory) are real, so its rank goes into ranker8. `CART_VIEWS` hurts rules5 (main hit3 +3.8 ± 1.2 when off); rules5
itself was not changed.

### Selection (3 cuts, all rows, against ranker3's inputs + rules5_rank)

| variant | main hit3 | main hit10 | new hit3 | new hit10 | carted today hit3 |
|---|---|---|---|---|---|
| ranker8 set, train2 parameters | +0.2 ± 1.7 | +2.0 ± 1.4 | −0.6 ± 2.3 | −1.2 ± 1.6 | −7.5 ± 3.9 |
| ranker8 set, train8 parameters (chosen) | +2.2 ± 1.6 | +3.3 ± 1.4 | −0.6 ± 2.3 | −1.5 ± 1.9 | −6.7 ± 3.7 |

### Test, 19:00–22:00 UTC, 579 purchase requests (hit1 / hit3 / hit10)

| strategy | main (325) | new_shopper (226) | no_views (28) | carted today (140) |
|---|---|---|---|---|
| ranker2 | 29.5 / 56.3 / 88.0 | 42.0 / 67.7 / 88.9 | 25.0 / 53.6 / 71.4 | 34 / 64 / 83 |
| blend1 | 30.8 / 58.5 / 88.6 | 43.8 / 70.4 / 92.0 | 28.6 / 46.4 / 85.7 | 55 / 79 / 92 |
| rules5 | 24.3 / 40.3 / 70.2 | 32.7 / 58.4 / 84.5 | 28.6 / 57.1 / 85.7 | 68 / 94 / 99 |
| ranker8 | 33.8 / 59.4 / 87.7 | 41.6 / 67.7 / 90.7 | 28.6 / 64.3 / 100 | 55 / 84 / 97 |

| paired ranker8 − | main hit1 | main hit3 | main hit10 | new hit1 | new hit3 | new hit10 | all hit3 | carted today hit3 |
|---|---|---|---|---|---|---|---|---|
| ranker2 | +4.3 ± 2.5 | +3.1 ± 2.7 | −0.3 ± 1.7 | −0.4 ± 3.7 | 0.0 ± 3.5 | +1.8 ± 2.4 | +2.2 ± 2.1 | +20.7 ± 3.3 |
| blend1 | +3.1 ± 2.1 | +0.9 ± 2.1 | −0.9 ± 1.6 | −2.2 ± 3.1 | −2.7 ± 2.7 | −1.3 ± 2.0 | +0.3 ± 1.7 | +5.7 ± 3.2 |

ranker2, blend1 and rules5 logged most of these lists themselves (hit@k favours the logging arm); ranker8 logged none.
Replay compute per request (recommend + guard): ranker2 12 ms, blend1 12 ms, ranker8 12 ms, rules5 1.7 ms.

## Verdict
- Real: product appeal / conversion, session relation, phrase taste, today's carts, history carts, shopper shares, context, and
  click × buy. Noise: price, session shape, today's views, cart times, own-list clicks, both multipliers. Harmful: slot as an input
  (the model is scored at slot 1 and learns position more than taste) and co-views (new shoppers).
- rules5's rank is the largest single gain (main hit3 +7.6, new hit3 +9.0, today-cart hit3 +15.8, all beyond 3 se).
- ranker8 (35 inputs) **ties** ranker2 and blend1 on the held-out window: every route difference is within about 1.7 se. Upside:
  main hit1 +4.3 ± 2.5 against ranker2, today-cart purchases hit1 +21 ± 4 and hit3 +21 ± 3, home hit10 +29 ± 8 (28 requests).
- It does not beat blend1 for new shoppers (hit3 −2.7 ± 2.7).

## Next
- Live trial of ranker8 against blend1 (files: `src/q2q/strategies/ranker8.py`, `models/ranker8.txt`, `models/ranker8_buy.txt`;
  train with `uv run python -m q2q.train8`).
- rules5 without `CART_VIEWS` (main hit3 +3.8 ± 1.2) as rules6; ranker8 would then read its rank.
- Selection cost 6.7 ± 3.7 points of today-cart hit3 against ranker3's inputs + rules5_rank; keeping `viewed_today` is the first thing to retry.
