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
- 14 Nov 15:15 · **Strategy names are no longer public.** The leaderboard shows every team's `model_version`. Ours is now an opaque code (`strategy.label`), decoded locally. Other teams could read `rules`, `rules2`, `rules3` and our commit sha until now.
- 14 Nov 15:15 · Leaderboard format changed: the JSON has `limits` (step 300 s, window 900 s to 10,800 s) and `custom`, so the page offers custom windows. Top teams: 1.73, 1.63, 1.51. Reference 2.0.
- 14 Nov 15:40 · **Cold requests get their own arms.** `arms.toml` has `[routes]`: `no_views` (home page) and `new_shopper`. First cold strategy `cold1` for requests without recent views: best-seller counts as base, the shopper's favourite category as a power law, viewed-not-bought ×4, segment. It runs two blocks on, two off, so it is not confounded with the `rules3`/`rules2` alternation.
- 14 Nov 15:40 · Public model names are now unrelated Catalan food words (`strategy.PUBLIC`).
- 14 Nov 15:40 · Block length stays 10 minutes while we read the one-hour window by subtraction. It moves to 15 minutes once we can read the 15-minute window directly.
- 14 Nov 15:55 · Public model names are minerals, approved by Santi (`strategy.PUBLIC`).
- 14 Nov 15:40 · **`rules3` dropped.** Two blocks at +19.2 and +19.3 against +25.4 for `rules2`. The steeper favourite-category effect hurts when the shopper has recent views. `rules2` runs alone, so `cold1` on home requests is the only thing alternating.
- 14 Nov 15:50 · **The leaderboard now scores each model directly**, for any window from 15 minutes to 3 hours (`/api/state?by=model&from=&to=`, found on the page's change list). `q2q board [minutes]` reads it. This replaces the block subtraction as the decision metric.
- 14 Nov 15:50 · **Arms now split shoppers by hash at the same time**, not by 10-minute block: the direct reading needs no time blocks, and a simultaneous split removes drift. Labels carry a route suffix (`-h` no views, `-n` new shopper) so arms are compared on the same kind of request.
- 14 Nov 15:50 · Direct reading, last hour: `rules2` 1.68–1.71% (score 32), `rules3` about 1.4%, `rules` 0.87%, baseline 0.74%, reference 2.13%. Confirms dropping `rules3`.
- 14 Nov 15:50 · `scripts/site_changes.py` tracks the organisers' change list into `docs/EVENT_CHANGES.md`.
- 14 Nov 16:10 · **First trained model live: `ranker`** (public name `jasper`), LightGBM on 601,187 live impressions with 1,794 clicks. On the newest 20% of requests: AUC 0.777 against 0.710 for the slot alone. Most important inputs: favourite-category share 20%, slot 19%, appeal 11%, segment 11%, same category as the session 9%. It gets 25% of ordinary requests and retrains every 20 minutes. Known weakness: it rarely re-shows recent views, because the training data is mostly best-seller lists where those were almost never shown.
- 14 Nov 16:10 · Explore share raised from 3% to 5%: the ranker needs outcomes on products the champion does not show.
- 14 Nov 16:10 · From now on several challengers run at the same time on slices of shoppers, each read directly on the per-model leaderboard.
- 14 Nov 16:20 · First split readings, 30-minute window: on requests without views `cold1` 0.45% and `rules2` 0.53% over about 350 requests each, no difference yet and both near the baseline. New shoppers with views convert at 2.28% on `rules2` (740 requests), ordinary returning shoppers at 1.64%. `ranker` 2.18% on its first 122 requests, too few to rank.
- 14 Nov 16:30 · **Practice traffic goes to learning, not to the champion** (Santi). The champion keeps only the share it needs as a control, one equal slice. `ranker` raised to 50% of ordinary requests. The final is the only time the champion runs nearly alone.
- 14 Nov 16:35 · **`ranker` promoted to champion.** It led `rules2` in two 30-minute windows on both kinds of request with views: 1.54% against 1.29% for returning shoppers (1,270 and 1,584 requests), 2.41% against 2.29% for new shoppers. `rules2` stays as the control arm.
- 14 Nov 16:35 · **Home page: the signal is the cart, not the view** (H-home-ceiling). Products a shopper added to the cart in history and never bought made 16 of 24 home purchases of returning shoppers; a product only viewed is barely better than one never seen. The live state now holds history carts per shopper and the products each shopper viewed today (organic events, refreshed every 5 s). `cold2` (public name `agate`) uses both and replaces `cold1` on half of home requests. I raised its cart weight from the subagent's ×5 to ×20 so carts lead the list, since the measured gap is ×14 to ×54.
- 14 Nov 16:35 · **Category pages are not a leak** (H-category-page). With recent views they convert at 2.02% against 1.85% for product pages; the earlier 0.6–0.7% was one noisy window. View age does not matter and `Request` needs no view timestamps (H-view-age rejected).
- 14 Nov 16:35 · `rules4` (public name `onyx`) in test on a third of ordinary requests: the first recent view leads and the session's category is the one with most views (H-reshow-rank, H-session-shape).
- 14 Nov 16:35 · Wide-feature study, interim: 185 features lift click AUC from 0.777 to 0.821 and purchase AUC from 0.872 to 0.909 on live data. Largest new signal: the shopper's history share of the product's feature phrases, ahead of the slot. A model trained on history does not transfer to live purchases.
- 14 Nov 16:40 · **The past-view bonus was really the cart, on every page.** On best-seller lists outside the session category, a carted-not-bought product gets ×5.6 clicks and ×6.1 purchases; a product viewed and never carted gets ×1.0. `rules4` now weights carts ×6 and drops the viewed-only bonus, so its readings from 16:37 include three changes at once (first view, main category, carts). The `ranker` does not see carts yet.
- 14 Nov 17:00 · **The operator runs** (`scripts/night_operator.py --apply 900`, log in `logs/operator.out.log`). Every 15 minutes it reads our per-model lines for the last hour. It drops an arm that is 2 standard errors below the best of its list with 800 requests each, and promotes a challenger that is 1.3 standard errors above the champion over the hour and ahead in both half hours. It only removes or reorders arms already in `arms.toml`, never empties a list and never drops the champion. Each run is a row in `team_01.scratch` (`kind = 'operator'`) and each change a line here. To stop it, kill both of its processes.
- 14 Nov 17:00 · First readings of the new arms, 30 minutes: `rules4` 1.64% (652 requests) against `ranker` 1.47% and `rules2` 1.38%; on the home page `cold2` 0.56% (338) against `rules2` 0.37%. Too few requests to act.
- 14 Nov 17:15 · **`ranker2` in test** (public name `shale`) on a third of ordinary requests, in place of `rules2`, which stays as the control on the home page. It adds 13 inputs from the wide-feature study and the session findings (phrase affinity, carts, co-views, first view, main category, today's views) and a trained purchase model instead of the fixed 81% / 27% rule. Offline on the newest 20%: click AUC 0.833 against 0.756, and the purchased product is in its top 3 in 74% of requests against 57%. It retrains every 20 minutes (`q2q train2 1200`). Second 30-minute reading of `rules4`: 1.59% against 1.32% for `ranker` and 1.34% for `rules2`; new shoppers 2.33% against 1.87% and 1.72%.
- 14 Nov 17:25 · **We are 14th of the teams over the last hour** (1.34%, score +27.5; the leader `team_06` 2.27%, +59). Our team number is a mix: about half the requests at 1.2–1.8%, new shoppers at about 2.2%, the home page (20%) at 0.5% and explore (5%) at 0.25%. Practice traffic went to experiments, including a champion (`ranker`) that fell to 1.16% in the last window. Decision: stop spreading. `rules4` is champion (1.81% over 1,012 requests, ahead for three windows), `ranker2` the only challenger (1.99% on its first 320), `ranker` and `rules2` out, `cold2` takes all home requests (0.59% against 0.41%), explore down to 2%.

**14 Nov 17:30 UTC.** History rows in ranker2's training: tested five ways, no gain on the top-3 share (72.2% against 71.4%, inside the noise). Left off. ranker2's first 30 minutes: 1.94% ordinary, 3.14% new shoppers, both ahead of rules4. See `docs/hypotheses/H-history-pretrain.md`.

**14 Nov 17:40 UTC.** Way of working changed after Santi's concern about pace. Online research done (`docs/findings/09-research.md`): diversity is worth almost nothing at our purchase rates; better candidates and the simulator's own form matter. Launched: a replay evaluator to filter ideas in minutes, a log-linear fit of the simulator's scoring form (`linear1`), the gap study (`rules5`). First test of a new signal: a product clicked through our own list and not bought, shown again, is bought in 1.1% of impressions (7 of 636).

**14 Nov 17:48 UTC.** Gap study done (`docs/hypotheses/H-gap.md`): the gap to the leaders is on pages with views, not home. Biggest miss: products carted today in the live stream (6.4% per weighted impression for new shoppers against 1.2% for the first view; 47 purchases, so plan on half). `rules5` (garnet) built on it and live on a third of ordinary requests. State now loads every cart of the live stream at start, not only the last 2 hours. Price-cut boost dropped in rules5: no live support.

**14 Nov 18:10 UTC.** Log-linear fit of the simulator (`H-loglinear`): rejected as a ranker (top 3 62.4% against 73.8% for ranker2); only half of the multipliers are stable across the day. Kept: click grows as appeal^1.5; the history-cart effect is x2.5 only for shoppers with a cart rate of 0.08 or more. Replay evaluator validated (`docs/findings/10-replay.md`): `hit10_other` with held-out models orders four arms as live did; it is now the filter before live traffic. ranker2 added to half of home requests on its offline result.

**14 Nov 18:10 UTC.** Prod moved to the VM (`Server_2`, 1 GB): router and operator as systemd services. Shadow run of 15 minutes first: 0 late answers, 490 MB, 3% CPU. Latency seen by the organisers unchanged (mean 1.1 s, p95 1.8 s). Cutover cost 63 fallback requests. Training stays on the laptop (890 MB, does not fit) and `scripts/push_models.py` pushes each new model. Deploy with `scripts/vm.sh`.

**14 Nov 18:28 UTC.** `ranker2` promoted to champion: ahead of rules4 on ordinary requests in three readings (2.09% and 1.92% against 1.80% and 1.16%), ahead on new shoppers in the last (2.42% against 1.71%). rules4 out; rules5 challenger on half (1.46% in its first window, above rules4, below ranker2). Team rank over 60 minutes: 14th at 17:20, 9th at 18:25.

**14 Nov 18:50 UTC.** Santi away. Prod is self-sufficient on the VM: ranker2 champion, rules5 challenger, operator every 15 minutes. Work queued at the end of the backlog in `strategies.toml` (QUEUED 1–4): finish ranker3; H-drift, Santi's hypothesis that parameters we treat as fixed move over time; retraining without the laptop; Sunday freeze.

## 14 Nov 21:12 UTC · rules5 off ordinary traffic, ranker2 alone
- Live, 3 h to 21:00: ordinary requests ranker2 1.94% (8,284) vs rules5 1.58% (8,570); new shoppers 2.78% vs 2.63% (2 h). rules5 behind in every window since 17:20. `schedule = ["ranker2"]`.
- Home stays split cold2 / ranker2: 0.55% vs 0.56% over 2 h, a tie.
- ranker3 retest on data to 21:00 (holdout3, 552 purchases): tie again with ranker2 (ordinary top 3 +0.3 ± 1.8, new shoppers top 1 +3.7 ± 2.8, top 3 -0.5 ± 2.8). Not deployed.
- Tried ranker4 = ranker2 with up to 3 of today's carts pinned on top. Replay: carted-today purchases top 1 63% vs 33%, but all purchases top 1 21% vs 36%: shoppers with carts today mostly buy something else. Rejected, file deleted. Carts today are 26% of purchases (144 of 552).
- Laptop slept 19:47 to 20:57 UTC: ranker2 on the VM was the 19:34 model for 90 minutes. train2 restarted by itself.
- Team: 11th of 42 over 60 min (+38.7), 9th over 3 h. Leaders team_06 +59, team_14 +57, team_03 +56 (one model, 2.19% on all traffic).
- 14 Nov 21:38 UTC · blend1 (rank fusion of ranker2 and rules5) on half of ordinary and new-shopper traffic through the operator queue. Offline: top 10 +3.4 ordinary, new shoppers top 1 +3.1, ordinary top 1 -2.2. Operator now rematches tested candidates when the queue is empty, promotion bar z 1.8.

## 14 Nov 22:10 UTC

- **Public names of variants.** A variant or ablation of a model now shows as the model's public word plus a capital letter (`strategy.VARIANT`): `blend1` is `shaleB`, was `m5c9e7`. The evaluation adds up an arm seen under two labels, so the running trial is not split. Router restart at 22:07 cost 72 fallback answers.
- **Drift test (H-drift): no change to training.** Product, brand and phrase rates do not drift today or over 59 days. The only moving part is the 2-hour subcategory bursts. Retraining faster than 20 minutes, a recent window only, and recency weights all tie or lose. A model 60 minutes old ties.
- **Per-request SQL (H-sql-neighbours) started.** A session-neighbour query takes about 300 ms, with some runs over 1 s, so it needs a 600 ms timeout and a fallback.

## 14 Nov 22:35 UTC

- Clean window 22:15–22:30 UTC, champion only, no exploration: 8th of 42, +40.9 (top +54.8). Same place as with trials running, so trials are not what holds us back.
- Per kind of request in that window: ordinary 1.80%, new shoppers 2.80%, home page 0.54% on 21% of requests, equal to the baseline 0.57%. Santi: the home page is the gap to close; focus there.
- Rejected offline: ranker6 (bagging, tie, 76 ms), ranker7 (organic buy model, worse alone), knn1 (per-request SQL neighbours, tie at best, 350 ms).
- ranker8 (ablated inputs plus rules5 rank) ties offline with upside: queued on ordinary requests after blend1, and on the home page now. Trainer runs on the laptop every 30 min.
- Started: hot1 (home page from SQL aggregates) and a diagnosis of who home-page shoppers are (H-home-who).
- Rejected offline: hot1 (cold2 times live buys per view plus two history multipliers). +1.2 pts organic top 10 over cold2, all of it from the history multipliers; below ranker2 (5.7% vs 6.3%). Live product counts add nothing for the home page. 38% of organic home purchases are re-buys we may not show.
- H-home-who: home shoppers buy organically as often as everyone else (10.4% vs 10.3% in 30 min); what home lacks is session intent. Today's carts convert ×2.5 history carts and ×5 other products inside the same home lists, and our lists show 22% of them. Repurchase looks best on organic hit rate but sells 0 live, so organic10 must not pick home arms.
- Built pin1 (ranker2 with up to 3 of today's carts pinned first). Queued on the home route after ranker8, live trial only (ranker4, a similar pin, lost an all-routes replay, but this evidence is home-specific and live).

## 15 Nov 03:30 UTC

- Operator verdicts: blend1 retired on ordinary requests (z 0.3); ranker8 retired on the home page (z 0.0). ranker8 kept on ordinary requests after 150 min. Last 60 min: ranker2 +55.4, ranker8 +52.0 on ordinary requests, ranker8 +69.5 vs ranker2 +64.3 on new shoppers. Noise.
- Operator bug: trials are keyed by strategy name across routes, so ranker8, still on trial for ordinary requests, was re-queued on the home page instead of pin1. Fixed by hand at 03:27: pin1 replaces ranker8 on the home page, queue no_views = ["pin1"]. Not fixing the code before the final.
- VM services now restart after any crash with no give-up limit (systemd drop-in, 14 Nov night, untested on purpose).

## 15 Nov 06:05 UTC: exploration over

- Last 3 h (06:00): ordinary ranker2 2.02% vs ranker8 1.96%; new shoppers ranker8 2.73% vs ranker2 2.42% (z about 0.9); home ranker2 0.59%, cold2 0.51%, pin1 0.48% (operator: pin1 z -0.5, retired). The home-page ideas did not beat ranker2 live.
- Operator stopped for good; queue empty. Arms set by hand: ranker2 on ordinary and home requests; new shoppers split ranker2 / ranker8 until 08:00 to decide that route. explore_share 0.02 until the freeze.
- Restart rehearsal at 06:02: router back and answering within about 60 s, 0 errors; first window after restart compute 37 ms/req, max latency 2.7 s (warm-up).

## 15 Nov 06:20 UTC: lock1 on half of main

A fresh-eyes agent, given only the problem, found in live feedback that 45% of our slots sit outside the last view's category and convert at half the rate; lists with 9-10 in-category items convert 4.1% against 1.1% (observational). lock1 = ranker2's scores, row filled from the last view's category first (shadow: 10.0 of 10 in category against 4.5, 7 ms). Main route split ranker2 / lock1, edited on the VM by hand. The router restart for its label cost 78 unlabelled answers in minute 06:18. Decision at about 07:30: if lock1 leads, it becomes the main champion. Note: the laptop dashboard's sync overwrites the local arms.toml, so edit arms on the VM.

## 15 Nov 06:30 UTC: lock2 on half of the home page

Home requests have no recent views, but 82% of those shoppers viewed products earlier today (shadow, 200 requests). lock2 treats today's last 5 organic views as the recent views and runs lock1. Label is its hash, md2ddd-h, so no router restart. Read at about 07:30 with lock1.

## 15 Nov 06:28 UTC: lock3, a soft lock, as a third arm on main

Case study of 546 purchases on view requests, last 3 h: 56% in the last view's category; about 117 (21%) cross-category, mostly Books & Media and Toys & Baby, half from slot 1, which lock1 would drop. lock3 multiplies in-category scores by 2 (shadow: 7.7 of 10 in category). Main split ranker2 / lock1 / lock3, label m461a2.

## 15 Nov 06:33 UTC: price1 as a fourth arm on main; second fresh-eyes agent

price1 = ranker2 x (1 + 0.5 x price percentile in category); shadow mean price shown 53 EUR against 41. Label mfd3c3. Main is now ranker2 / lock1 / lock3 / price1. A second fresh-eyes agent studies purchases our known factors do not explain, and price.

## 15 Nov 06:35 UTC: Santi: test candidates until the freeze rather than play safe; seen1 on new shoppers

Santi prefers that untested candidates get live trials before 08:30 over spending the time on reliability. No more router restarts (new arms use hash labels). seen1 = the last two viewed products in slots 1-2, then ranker2; new-shopper route split ranker2 / ranker8 / seen1, label m7ff44-n.

## 15 Nov 06:42 UTC: goal top 5; aff1 and super1 live on every route, lock1 and price1 dropped

Santi: the goal is top 5, do things differently. Per-arm read 06:35 (35 min): lock1 +33 against ranker2 +52 on main, dropped. ranker8 beats ranker2 for new shoppers over 3 h (+78.5 against +63.1, 3.8k requests each): ranker8 is now the new-shopper base. Second fresh-eyes agent: a shopper's live purchase share of a category multiplies conversion up to x4 (monotone, within buyers); subcategory live rates spread 10x; a few products trend. aff1 = ranker2 x affinity (mac5e8). super1 = ranker2 x affinity x last-category x2 x live subcategory rate x hot product, home page uses today's views (m6eb87). Price showed no penalty but no clear gain: price1 dropped. Arms: main ranker2/lock3/aff1/super1, home ranker2/aff1/super1, new shoppers ranker8/seen1/aff1/super1.

## 15 Nov 07:00 UTC: first read of the new arms; seen1 dropped; laptop offline about 07:10-08:00

18 min since the 06:42 reset: main lock3 +71.7 (487 requests) against ranker2 +48.2 (485), super1 +53.7, aff1 +49.6; new shoppers ranker8 +90.5, aff1 +72.9, seen1 +45.5; home ranker2 -2.5, aff1 -4.4. seen1 dropped; lock3 joins the new-shopper route. Small samples. The arms keep running on the VM while the laptop is offline (no retraining for about 50 min: models about 70 min old by 08:00, within the 60-min tie range).

## 15 Nov 07:05 UTC: public-simulator research and the competition test

A research agent listed the likely templates (position-based click model plus a purchase step, cascade, multinomial logit with an outside option, RecoGym-style latent factors, a hand-written persona generator). Competition test on 8 h of feedback (about 72k lists): slot-2 click rate does not fall when the slot-1 item is strong (strong slot-2 items: 1.69% / 1.51% / 2.18% with weak / mid / strong slot 1). No sign of items stealing each other's click, so per-item scoring and sorting by P(buy) stays right; no assortment trick to exploit.
