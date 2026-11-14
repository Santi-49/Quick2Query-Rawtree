# Journal

Dated decisions: promotions, switchovers, incidents. Times are UTC.

- 14 Nov 13:10 · Plan approved by Santi, stratified explore arm chosen. Build started.
- 14 Nov 13:26 · Switchover: starter stopped, `q2q serve` took over on the laptop. 26 requests went to the fallback. Champion `baseline`, explore 3%.
- 14 Nov 13:28 · `rules` on alternate 10-minute blocks against `baseline`.
- 14 Nov 13:36 · **`rules` promoted to champion after 8 minutes, not three block pairs.** Leaderboard: us 0.777 against baseline 0.707 over the hour with only 7 minutes of `rules` in it. That is about +7.6 expected purchases in 1,260 requests, a `rules` conversion near 1.3% (score about 20), against a noise floor of 0.5 purchases. The leaderboard's baseline row covers the same shoppers, so our own baseline blocks are not needed as a control. From now on blocks alternate only between champion and a challenger.
- 14 Nov 13:36 · Reference 2.01%, best team 1.44%. The leaderboard refreshes every minute since 12:46.
- 14 Nov 13:36 · First block of `rules`: +16 score (lift +8.5 expected purchases in 1,800 requests). Reference window score about 45.
- 14 Nov 13:43 · **Live calibration (H-live-factors) contradicts three history-based multipliers.** Recent views are worth ×11, not ×35. The shopper's favourite category is worth about ×10–20, not ×2. A past view is a flat ×3. Challenger `rules2` carries the live values and alternates with `rules` per block. Risk noted: favourite category and past views overlap, and the calibration data is 94% best-seller lists, so `rules2` may over-score favourites against the current session. The blocks decide.
