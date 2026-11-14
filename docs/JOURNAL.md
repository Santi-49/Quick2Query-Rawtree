# Journal

Dated decisions: promotions, switchovers, incidents. Times are UTC.

- 14 Nov 13:10 · Plan approved by Santi, stratified explore arm chosen. Build started.
- 14 Nov 13:26 · Switchover: starter stopped, `q2q serve` took over on the laptop. 26 requests went to the fallback. Champion `baseline`, explore 3%.
- 14 Nov 13:28 · `rules` on alternate 10-minute blocks against `baseline`.
- 14 Nov 13:36 · **`rules` promoted to champion after 8 minutes, not three block pairs.** Leaderboard: us 0.777 against baseline 0.707 over the hour with only 7 minutes of `rules` in it. That is about +7.6 expected purchases in 1,260 requests, a `rules` conversion near 1.3% (score about 20), against a noise floor of 0.5 purchases. The leaderboard's baseline row covers the same shoppers, so our own baseline blocks are not needed as a control. From now on blocks alternate only between champion and a challenger.
- 14 Nov 13:36 · Reference 2.01%, best team 1.44%. The leaderboard refreshes every minute since 12:46.
- 14 Nov 13:36 · First block of `rules`: +16 score (lift +8.5 expected purchases in 1,800 requests). Reference window score about 45.
- 14 Nov 13:43 · **Live calibration (H-live-factors) contradicts three history-based multipliers.** Recent views are worth ×11, not ×35. The shopper's favourite category is worth about ×10–20, not ×2. A past view is a flat ×3. Challenger `rules2` carries the live values and alternates with `rules` per block. Risk noted: favourite category and past views overlap, and the calibration data is 94% best-seller lists, so `rules2` may over-score favourites against the current session. The blocks decide.
- 14 Nov 14:20–15:04 · **Outage, 44 minutes on the fallback.** The laptop went into standby (power button, then lid). Router and logger resumed alone on wake. Block readings now fill a gap in the leaderboard log: the gap's total lift is shared out by our answered requests.
- 14 Nov 15:08 · **`rules2` promoted to champion** on two block pairs instead of three: +29.8 and +19.7 against +18.1 and +15.2 for `rules`. Mean +24.8 against +16.5. Promoted early because alternating costs half the traffic and usage is limited.
- 14 Nov 15:08 · Challenger `rules3`: favourite category as a power law, (share / 10%)^1.5, from H-home-personal (history ×28 at a 60% share, live clicks agree in shape). Risk: it ranks favourites above the current session more often.
- 14 Nov 15:08 · Subagents stopped at the usage limit at about 14:45. Done: H-live-factors, H-home-personal, the HTML explainer file exists unreviewed. Not done: cold-prior, first-view, home-best-list write-ups (SQL exists), all affinity hypotheses.
