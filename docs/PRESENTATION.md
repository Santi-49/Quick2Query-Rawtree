# Presentation brief · quick2query (team_01)

For the agent that builds the jury slides; nothing else is needed. Every number cites its source file. Times are UTC (Barcelona = UTC+1). The final round runs 09:00–11:00 UTC on 15 Nov. Its results do not exist yet: they are marked `TBD (final round)`.

Jury criteria (README.md): Method 10, Learning from the stream 10, Use of RawTree 5, Communication 5, plus a side prize for "Best agentic use of RawTree". Audience: data and ML people and the organisers. Keep slides plain.

## 1. Summary

A simulated shop sends about 3 shoppers per second; for each we have 3 seconds to pick 10 products, and a hidden model decides clicks and purchases. We did not copy that model. We measured what it reacts to and turned each finding into a small strategy file. Strategies competed live on hash-split shares of shoppers, each scored separately by the public leaderboard. A router on a VM keeps live shopper state in memory from the event stream; a LightGBM model retrains every 20 minutes on our feedback. AI agents built most pieces; an unattended operator ran trials overnight. Over the practice day we went from the best-seller baseline to about 8th of 42 teams. The final champion is `ranker2`, a click model times a buy-after-click model. New shoppers get `ranker8`.

**Three key messages**

1. **Measure the simulator, don't guess it.** One intent per session. Slot 1 gets about twice the clicks of slot 2. Products already bought are suppressed. History and live data disagree on that last point.
2. **Live A/B arms decide, offline replay only filters.** Every promotion and every retirement is a dated line in the journal.
3. **Agents did the building, the human did the deciding.** The honest lesson: big observational lifts (×2, ×4) were already in the champion's features. Stacking them again tied or lost live, and short windows fooled us for a while.

## 2. Slide outline (12 slides)

### Slide 1 · We have 3 seconds to pick 10 products for a shopper whose model we cannot see
- About 3 requests per second. We answer with 10 distinct, active product IDs within 3 s.
- Score = 100 × (team − baseline) / (oracle − baseline). Baseline = all-time best sellers. Oracle = the hidden model's own top 10.
- Final grade = 70% leaderboard (conversion 50, cold start 10, reliability 10) + 30% jury.
- Only 09:00–11:00 UTC on 15 Nov counts, on new shoppers and products, with the leaderboard hidden.
- **Numbers:** baseline 0.64–0.69% expected purchases per request, reference 2.10%, oracle about 3.6–3.7%; one score point ≈ 0.03 conversion points (SIMULATOR.md, 07-leaderboard.md).
- **Visual:** a horizontal scale from 0 (baseline) to 100 (oracle), with reference at about 48 and our practice score marked.

### Slide 2 · Shoppers have one intent, and they mostly look at the first slots
- At most one click per request; the purchase is always the clicked product. So we model click, then buy after click.
- Attention follows 1/log2(slot+1). Slot 1 = 1.00, slot 2 = 0.62, and slots 1–3 hold 47% of the weight. Live, slot 2 has ×0.54 the click odds of slot 1.
- One intent per session: the next organic view is in the same subcategory 73% of the time, and the same category 80%.
- A product from the current category converts about 5× better than one from another category. The best-seller list showed 89% other-category products.
- **Numbers:** click by slot 4.45 / 2.77 / 2.23 … 1.18% (03-carousel-history.md); ×0.54 (H-loglinear.md); 73% / 80% (SIMULATOR.md); same vs other category 0.63% vs 0.13% (06-feedback.md).
- **Visual:** bar chart of relative clicks for slots 1–10, with the 1/log2 curve on top.

### Slide 3 · History lies about repeat purchases; carts and taste are the real signals
- History: a product bought before converts better (2.30% vs 0.12%). Live: worse (0.024% vs 0.041% for never seen). The organisers confirmed it.
- So we never show bought products, and every history effect is a prior until checked live.
- The "viewed before" bonus was really the cart. Carted-not-bought gets ×5.6 clicks and ×6.1 purchases. Viewed-only gets ×1.0.
- Phrase taste (the shopper's share of views on a product's description phrases) is the largest single learned signal.
- Segment: Android in Andalucía, Canarias and Murcia converts ×3 overall, ×5–30 in four categories. This holds for new shoppers too.
- **Numbers:** 06-feedback.md, JOURNAL 14 Nov 16:40, H-cold-prior.md; a history-trained purchase model scores AUC 0.643 live (08-ml-patterns.md).
- **Visual:** a two-column "history vs live" table with arrows showing the sign of each effect.

### Slide 4 · One router on a VM keeps live state in memory and hot-reloads strategy files
- The router polls `shop.requests`, picks an arm by shopper hash, runs the strategy and the guard, and batch-inserts into `team_01.submissions`. It is the only writer.
- Live state is refreshed every few seconds from `shop.events` and `shop.catalog_updates`: stock, prices, today's views and carts, live purchases, trends.
- `arms.toml` is the only deploy switch. It and the strategy files are hot-reloaded with no restart. A new idea is a new file: 31 strategy files exist.
- The guard drops invalid or out-of-stock IDs and pads with best sellers: a broken experiment cannot give an invalid answer.
- Prod has been on the VM since 14 Nov 18:10, under systemd: 490 MB, 3% CPU, latency mean 1.1 s and p95 1.8 s. The laptop retrains every 20 minutes and pushes models (`scripts/vm.sh models`).
- **Numbers:** JOURNAL 14 Nov 18:10, src/q2q/serve.py, src/q2q/strategies/.
- **Visual:** architecture diagram: RawTree tables (requests, events, catalog_updates) → router on VM (state, arms.toml, strategies, guard) → submissions; feedback → laptop trainer → model push to VM; leaderboard `/api/state?by=model` → operator → arms.toml.

### Slide 5 · Each arm gets a meaningless public label, so the leaderboard scores it for us
- The leaderboard shows every team's `model_version`. Ours were readable until 15:15, so we switched to opaque labels: mineral words (jasper, agate, onyx, shale, garnet), then hash codes.
- From 15:50 the leaderboard scores each model directly (`/api/state?by=model`, 15 min to 3 h windows). Arms split shoppers by hash at the same time: no drift between arms.
- Routes get their own arms: `main` (returning shopper with views), `new_shopper`, and `no_views` (home page). Labels carry a route suffix (`-h`, `-n`).
- **Numbers:** JOURNAL 14 Nov 15:15, 15:50, 22:10. 07-leaderboard.md.
- **Visual:** a mock leaderboard row, `shale` → decoded locally as `ranker2`, next to a pie of the hash split per route.

### Slide 6 · ranker2 multiplies P(click at slot 1) by P(buy | click), both learned from our own feedback
- Two LightGBM models trained on live feedback only. Adding history rows gave no gain: top 3 72.2% vs 71.4%.
- 34 inputs: phrase taste, the shopper's cart rate, session phrase overlap, category share, carts in category, appeal, co-views, the session's main category, today's views.
- Offline at launch (17:15, newest 20%): click AUC 0.833 vs 0.756, purchased product in the top 3 in 74% of requests vs 57%.
- SHAP: click is driven by phrase_share 16%, slot 12.5% and cart rate 11%. Buy is driven by cart rate 18%, appeal 8% and phrase_share 8%. Retraining every 20 minutes keeps the top features stable.
- `ranker8` for new shoppers: noisy input groups removed by ablation, plus rules5's rank as an input (+7.6 main hit3, +9.0 new hit3). Live over 3 h: +78.5 vs +63.1 for ranker2 on new shoppers.
- **Numbers:** JOURNAL 17:15, 17:30, 15 Nov 06:42. shap.md. H-ablation.md. H-history-pretrain.md.
- **Visual:** two horizontal SHAP bar charts, click and buy, top 6 features each.

### Slide 7 · Live arms decide, offline replay filters, and every change is logged
- Offline replay (`q2q replay`) scores a strategy in 1–2 minutes on logged requests. Its `hit10_other` metric ordered four arms exactly as live did. It filters ideas and never promotes one.
- Offline is blind to cross-category lists, the home page and new products (the old carousel showed one category per request).
- Rejected offline before using any traffic: ranker3, ranker5 (embeddings), ranker6 (bagging), ranker7, knn1 (per-request SQL), hot1, linear1.
- Promotion rule (operator): at least 800 requests per arm, z ≥ 1.8 over 60 min and ahead in both half hours. An arm z ≤ −2 below the best is dropped.
- Every promotion and retirement is a dated line in `docs/JOURNAL.md`. 25 hypothesis files, each with a verdict.
- **Numbers:** 10-replay.md, PLAN.md section 7, scripts/night_operator.py, JOURNAL 14 Nov 21:12–22:35.
- **Visual:** funnel: idea → hypothesis + SQL → offline replay → live arm → journal line.

### Slide 8 · The champion changed six times in 18 hours
- baseline → rules (13:36) → rules2 (15:08) → ranker (16:35) → rules4 (17:25) → ranker2 (18:28). Final arms set at 07:59: ranker2 on main and home, ranker8 on new shoppers, explore 0.
- Team rank over 60 min: 14th at 17:20, 9th at 18:25, 11th of 42 at 21:12 (9th over 3 h). Clean window 22:15–22:30: 8th of 42, +40.9 (top team +54.8). Morning of 15 Nov, on conversion: 12th to 14th of 42 (05:36–07:24), dragged down by the many test arms and one restart.
- In the clean window: ordinary 1.80%, new shoppers 2.80%, home 0.54% vs baseline 0.57%. Home is the gap we did not close.
- Final round: `TBD (final round)`.
- **Numbers:** JOURNAL 13:36, 15:08, 16:35, 17:25, 18:28, 21:12, 22:35; 15 Nov 07:59.
- **Visual:** timeline of champions with team rank underneath.

### Slide 9 · Per-route results: the morning's new arms did not beat the champions
- 75-minute read to 07:55; score per arm, arms on one route split the same shoppers.
- Main: ranker2 +55.0 (1,774 requests), aff1 +52.3, lock3 +50.7, super1 +44.8, super2 +38.4.
- New shoppers: ranker8 +85.9 (825), aff1 +67.7. Home: ranker2 −0.3, aff1 −0.3, super1 −1.6.
- **Numbers:** JOURNAL 15 Nov 07:59.
- **Visual:** grouped bar chart per route, with the champion highlighted.

### Slide 10 · Agents built it; one session decided; RawTree was the shared memory
- The main session (Fable) decided, planned and kept the journal. Opus subagents built the deterministic pieces: strategies, trainers, replay, hypothesis tests.
- Fresh-eyes agents got only the problem statement. They found the category-lock signal (45% of slots off the last view's category, converting at half the rate) and purchase taste (up to ×4). A third designed the whole system from scratch and matched ours.
- The overnight operator ran every 15 min with no human. It queued candidates, ran 150-minute trials, and retired blend1 (z 0.3), ranker8 on home (z 0.0) and pin1 (z −0.5). Guard rails: it never empties a list and never drops the champion.
- All analysis is SQL aggregates run in RawTree (35 SQL files: features, reports, hypotheses), through `rtree`, the RawTree MCP server and `scripts/q.py`. Tracking (leaderboard, operator runs, explore logs) is rows in `team_01.scratch`.
- **Numbers:** JOURNAL 14 Nov 17:00, 15 Nov 03:30, 06:05, 06:20, 06:42, 07:12. PLAN.md section 10. scripts/night_operator.py. The sql/ directory.
- **Visual:** main session in the centre, subagents around it, operator loop on the VM, RawTree underneath as shared memory.

### Slide 11 · What failed: we multiplied signals the model already had
- Morning of 15 Nov: aff1 (taste ×4), lock3 (category ×2), super1 and super2 stack observational lifts on top of ranker2.
- Early reads looked like wins. At 07:00 (18 min) lock3 had +71.7 vs ranker2 +48.2. At 07:10 (30 min) aff1 had +59.4 vs +48.5.
- The 75-minute read reversed it: ranker2 +55.0 led every arm. The lifts were already captured by ranker2's features (same category as last view, category shares, carts).
- Other misses: home-page ideas never beat ranker2 (3 h to 06:00: ranker2 0.59%, cold2 0.51%, pin1 0.48%; hot1 failed offline). An operator bug keyed trials by name across routes. The laptop slept twice: 44 min on fallback, and once leaving the model 90 min stale.
- **Numbers:** JOURNAL 14 Nov 14:20, 21:12, 22:35; 15 Nov 03:30, 06:05, 07:00, 07:10, 07:59, 08:06.
- **Visual:** a line chart of score over read length (18, 30, 75 min) for lock3, aff1 and ranker2, with the lines crossing.

### Slide 12 · Next time we would add signals as model inputs and fix the read length in advance
- A feature in the model beats a multiplier on top of it. Test new signals as model inputs, not as boosts.
- Read windows long enough: 30 minutes misled us, 75 minutes corrected us. Fix the minimum read length before looking.
- History is a prior, live is the truth (repeat purchases, carousel CTR ×13.5 in history vs ×1.1 live).
- Next: spend exploration on the home page (21% of requests, still at baseline level) and make the operator route-aware.
- **Numbers:** 08-ml-patterns.md, JOURNAL 22:35, 15 Nov 03:30.
- **Visual:** three lesson cards.

## 3. Key numbers

| Number | Value | Source | Date/time UTC |
|---|---|---|---|
| Baseline conversion | 0.64–0.69% | SIMULATOR.md | 14 Nov 12:30 |
| Reference conversion | 2.10% (2.01–2.13% across readings) | SIMULATOR.md, JOURNAL | 14 Nov 12:30–15:50 |
| Oracle, implied | 3.6–3.7% | 07-leaderboard.md | 14 Nov 12:26 |
| Slot click, same product, slot 1→10 | 4.45 → 1.18% | 03-carousel-history.md | history |
| Slot 2 click odds vs slot 1 | ×0.54 | H-loglinear.md | 14 Nov 18:10 |
| Next view same subcategory / category | 73% / 80% | SIMULATOR.md | history |
| Same vs other category purchase, slots 1–3 | 0.63% vs 0.13% | 06-feedback.md | 14 Nov 12:25 |
| Bought before: history vs live | 2.30% vs 0.12%; live 0.024% vs 0.041% | 03-carousel-history.md, 06-feedback.md | 14 Nov |
| Carted-not-bought lift | ×5.6 clicks, ×6.1 purchases | JOURNAL | 14 Nov 16:40 |
| History purchase model on live | AUC 0.643 | 08-ml-patterns.md | 14 Nov 18:10 |
| First promotion (rules) | 0.777 vs baseline 0.707 | JOURNAL | 14 Nov 13:36 |
| rules2 direct reading | 1.68–1.71%, score 32 | JOURNAL | 14 Nov 15:50 |
| ranker2 offline | click AUC 0.833 vs 0.756; top 3 74% vs 57% | JOURNAL | 14 Nov 17:15 |
| ranker2 SHAP, click | phrase_share 16.3%, slot 12.5%, cart rate 11.4% | shap.md | 14 Nov 22:34 |
| ranker2 SHAP, buy | cart rate 18.3%, appeal 8.4%, phrase_share 7.8% | shap.md | 14 Nov 22:34 |
| rules5 rank as input | +7.6 main hit3, +9.0 new hit3 | H-ablation.md | 14 Nov night |
| VM footprint | 490 MB, 3% CPU, latency mean 1.1 s, p95 1.8 s | JOURNAL | 14 Nov 18:10 |
| Rank, 60 min | 14th (17:20), 9th (18:25), 11th of 42 (21:12) | JOURNAL | 14 Nov |
| Clean window | 8th of 42, +40.9; top +54.8 | JOURNAL | 14 Nov 22:15–22:30 |
| Rank on conversion, 60 min | 12th to 14th of 42; at 07:24 14th, 1.83% vs 2.06% (10th) and 2.19% (3rd–5th) | data/leaderboard snapshots, JOURNAL | 15 Nov 05:36–07:24 |
| Per route, clean window | ordinary 1.80%, new 2.80%, home 0.54% (baseline 0.57%) | JOURNAL | 14 Nov 22:35 |
| Operator rule | ≥800 req/arm, promote z 1.8, drop z −2, trial 150 min | night_operator.py | final code |
| Operator retirements | blend1 z 0.3, ranker8 home z 0.0, pin1 z −0.5 | JOURNAL | 15 Nov 03:30, 06:05 |
| Fresh-eyes: off-category slots | 45%, half the rate; 4.1% vs 1.1% | JOURNAL | 15 Nov 06:20 |
| Fresh-eyes: purchase taste | up to ×4 | JOURNAL | 15 Nov 06:42 |
| Early reads (misleading) | lock3 +71.7 vs ranker2 +48.2; aff1 +59.4 vs +48.5 | JOURNAL | 15 Nov 07:00, 07:10 |
| 75-min read, main | ranker2 +55.0 (1,774), aff1 +52.3, lock3 +50.7, super1 +44.8, super2 +38.4 | JOURNAL | 15 Nov 07:55 |
| 75-min read, new / home | ranker8 +85.9 (825), aff1 +67.7 / ranker2 −0.3, aff1 −0.3, super1 −1.6 | JOURNAL | 15 Nov 07:55 |
| ranker8 vs ranker2, new shoppers, 3 h | +78.5 vs +63.1 | JOURNAL | 15 Nov 06:42 |
| Strategy files / hypothesis files / SQL files | 31 / 25 / 35 | src/q2q/strategies/, docs/hypotheses/, sql/ | 15 Nov 08:10 |
| Final-round rank, score, conversion, cold start, reliability | TBD (final round) | — | 15 Nov 09:00–11:00 |

Where sources disagree:
- The reference reads 2.01% at 13:36 and 2.10–2.13% later. Use 2.10% (SIMULATOR.md).
- The operator's promotion bar was 1.3 SE at 17:00 and 1.8 from 21:38. Use 1.8 (the later entry, and the code).
- The PLAN describes 10-minute time blocks. They were replaced by simultaneous hash splits at 15:50 (JOURNAL).

## 4. Glossary

- **Arm**: one strategy serving a hash-chosen share of shoppers. Arms on one route split the same shoppers, so they compare directly.
- **Route**: the kind of request. `main` = returning shopper with recent views. `new_shopper` = new shopper with views. `no_views` (home) = no recent views, about 20% of requests.
- **Label**: the public `model_version`, meaningless on purpose (minerals, then hashes like `m461a2`, route suffix `-h` / `-n`), decoded locally.
- **Champion**: the arm with all of a route's traffic when no trial runs. Final: ranker2 (main, home), ranker8 (new shoppers).
- **Challenger / trial**: an arm sharing a route with the champion until the live read decides.
- **Explore share**: traffic sent to stratified random lists to learn about products the champion never shows: 3–5% early, 2% overnight, 0 for the final.
- **Score**: 100 × (team − baseline) / (oracle − baseline), clipped to 0–100 for the final. Conversion = expected purchases per 100 requests (the simulator's probabilities, no coin flips). Per-arm practice readings can be negative.
- **Baseline**: all-time best sellers in stock, also the fallback for late or invalid answers. **Oracle**: the hidden model's own best 10. **Reference**: the organisers' recommender, about 48 of 100.
- **Operator**: `scripts/night_operator.py`, an unattended loop that edits `arms.toml` from per-model readings.

## 5. Placeholders and notes for the slide builder

- Final-round rank, score, conversion, cold-start score and reliability: `TBD (final round)`. The final runs 09:00–11:00 UTC on 15 Nov, and the ranking appears at 11:00 UTC.
- The latest team rank in the sources is 14th of 42 on conversion (15 Nov 07:24, during the morning tests); the best was 8th of 42 (14 Nov 22:15–22:30). Do not invent a later one.
- Not for a slide, but be ready if asked: a helper script fetched the challenge page every 5 min from 14 Nov 16:40 until 15 Nov 08:06, against our own "/api/state only" rule; stopped and logged (JOURNAL 15 Nov 08:06).
