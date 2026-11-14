# 07 · Leaderboard and how fast we can measure

Source: `https://datathon.rawtree.dev/api/state`, the JSON behind the public page. Logged by `scripts/leaderboard_logger.py` into `team_01.scratch` (`kind = 'leaderboard'`) and `data/leaderboard/`.

## What the JSON holds

- Refreshed every 10 minutes, at xx:x6:35 UTC. Each refresh covers the last hour exactly (`window`).
- Per team, and for `baseline` and `reference`: `conversion` (expected purchases per 100 requests, full precision), `cold_conversion`, `on_time`, `revenue_per_request`, `requests`, `model_version`.
- `progress`: per team, one score from 0 to 100 per clock hour. The last point is the running hour.
- The oracle is not shown.

## Values

| Refresh (UTC) | Baseline | Reference | Best team | team_01 |
|---|---|---|---|---|
| 12:06 | 0.639 | 2.105 | 0.829 | 0.645 |
| 12:16 | 0.659 | 2.088 | 0.850 | 0.666 |
| 12:26 | 0.691 | 2.100 | 0.900 | 0.698 |

| Cold requests only | Baseline | Reference |
|---|---|---|
| 12:16 | 1.150 | 1.794 |

- 39 teams. Five or six are clearly above the baseline (0.83–0.90). Nobody is near the reference.
- The baseline moves with the stream: +8% in 20 minutes. Always compare inside the same window.
- The baseline converts better on cold requests than overall, the reference worse. Cold is where the reference is weakest.
- Teams answering nothing do not all equal the baseline (0.69, 0.75). Each team seems to have its own shopper state.

## Where the oracle is

`score = 100 × (team − baseline) / (oracle − baseline)`. Weighting each team's hourly `progress` scores over the window and dividing:

| Team | Refresh 12:06 | 12:16 | 12:26 |
|---|---|---|---|
| team_09 | 2.88 | 2.91 | 2.96 |
| team_20 | 2.92 | 2.97 | 3.03 |
| team_19 | 2.94 | 2.99 | 3.04 |

(oracle − baseline, in conversion points)

- **The oracle converts at about 3.6–3.7%.** One score point is about 0.03 conversion points.
- **The reference is worth about 48 of 100.** The best team is at about 7.
- Assumes `progress` is the conversion score. Our own values fit it (0.2 points for a 0.006 lead).

## How fast each instrument answers

| Instrument | Signal per hour, all traffic | Requests per arm to see +20% | To see ×2 |
|---|---|---|---|
| Purchases in our feedback | ~75 | ~57,000 | ~3,400 |
| Clicks in our feedback | ~260 | ~16,000 | ~1,000 |
| Leaderboard conversion | exact, no coin flip | one window | one window |

- Purchases cannot rank strategies before the final. Clicks can confirm a large effect within an hour on a 10% arm.
- The leaderboard is exact but scores the blend of everything we served in the hour.

## 10-minute resolution from the leaderboard (first check done)

Consecutive windows differ by one 10-minute block entering and one leaving. With `S = conversion × requests`:

```
S(t) − S(t − 10 min) = block entering − block leaving
```

Starting from an hour where every block is known (we serve the baseline list now, so our blocks equal the baseline's), each new block follows from the previous refresh. The same holds for the baseline, so every block can be read against the baseline on the same shoppers.

- This gives a reading per 10 minutes and per arm, if arms switch at the refresh times.
- It breaks if one refresh is missed. The logger must not stop.

First check, while we and the baseline both serve best sellers. Our block minus the baseline's block, entering minus leaving, in expected purchases (a block holds about 1,800 requests and 12.5 expected purchases):

| Refresh (UTC) | 12:16 | 12:26 | 12:36 |
|---|---|---|---|
| Us minus baseline | −0.02 | +0.13 | +0.57 |

- The floor is up to 0.03 conversion points per block, about 1 score point. The two lists are not identical (stock timing, own shopper state), so part of this is real.
- Good enough to separate strategies that differ by 3 score points or more in one block, and by 1 point over a few alternated blocks.
- Refresh times drift by 0–2 s. That moves about 6 requests between blocks, which is negligible.
