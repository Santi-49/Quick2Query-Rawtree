# 09 · Research: how simulators like ours are built, what wins session recsys, how to evaluate fast

Written 14 Nov evening from web sources plus our own docs (`docs/SIMULATOR.md`, `docs/findings/08-ml-patterns.md`, `docs/hypotheses/H-home-ceiling.md`). Nothing here was run against the database.

Labels used throughout:
- **[F]** fact stated by the linked source.
- **[I]** our inference, applied to our numbers. Treat as a hypothesis.

## The one thing to take away

**[I]** At our purchase rates (1–4% per list), "probability of at least one purchase" and "sum of purchase probabilities" are the same number to within a few percent: 1 − Π(1 − p_i) ≈ Σ p_i − Σ_{i<j} p_i p_j, and the pair term is around 0.01 × 0.01 per pair. The organisers also say the oracle is "the 10 products the hidden model would pick", which reads like top-10 by a per-product score. So **diversity for its own sake is worth almost nothing here**. The gains are in (a) better candidates, (b) a better calibrated per-product score, (c) using the state the simulator keeps per shopper. Hedging across intents only pays as part of (b): rank by E[p] under our uncertainty about intent, which already spreads a home list across categories when the intent is unclear.

## Top 10 ideas to try, ranked by expected gain per hour of work

### 1. Re-show what the shopper touched today, ours included, with calibrated multipliers
Treat every product the shopper carted or viewed **today** (organic `shop.events` and clicks or carts through **our** lists) as a first-tier candidate, next to history carts. Score each with a measured multiplier, not a fixed tier.
- **Evidence.** [F] Repeat and session items are the strongest candidate source in session competitions: OTTO solutions put all prior session items into the candidate set first, then co-visited items ([Fedorov OTTO repo](https://github.com/Fedorov-Artem/kaggle_OTTO), [NVIDIA OTTO repo](https://github.com/bschifferer/Kaggle-Otto-Comp)). H&M's winning write-up uses repurchase interactions as a retrieval strategy and as a feature ([H&M top 1 summary](https://goldandrabbit.github.io/2022/05/15/H&M%20Recommendation%20Competition%20Top1%20%E6%96%B9%E6%A1%88)). [F, ours] Carted-not-bought converts ×6–20 live; viewed today ×3 on new shoppers (H-home-ceiling).
- **Test (≤30 min).** On `team_01.feedback`, for each shown product label its relation: carted today organically, viewed today organically, clicked in one of our lists earlier today, carted through our list earlier today (add_to_cart without purchase in our feedback), history cart, none. Report clicks, buys and buys / Σ 1/log2(slot+1) per label. The new labels are the last two: if "carted via our list earlier" converts like a history cart, the simulator writes our feedback into shopper state.
- **Code.** In the candidate builder add the two "via our lists" sources from our feedback table (kept in memory by `serve`). In the ranker add features `today_cart`, `today_view`, `our_click_today`, `our_cart_today`. Keep "bought (anywhere, ever)" as a hard exclusion.

### 2. Fit the simulator's own form: a log-linear model on clean indicators
An AI-written simulator almost certainly computes purchase as a product of a few round multipliers (×3 if recently viewed, ×2 same category, segment boost, phrase match, price term) times a position weight. Fit that form directly.
- **Evidence.** [F] Reference simulators are built this way: RecSim scores a document by a mix of topic interest and latent quality and feeds it to a configurable choice model ([RecSim](https://arxiv.org/abs/1909.04847)); Open Bandit Pipeline's slate generator draws a base reward per context-action pair and adds a position effect of (1/k)^η under a `pbm` or `cascade` click model ([obp synthetic_slate.py](https://raw.githubusercontent.com/st-tech/zr-obp/master/obp/dataset/synthetic_slate.py)). [F, ours] 08-ml-patterns: interactions are weak (H² < 0.03 except carts × cart rate), "most of the structure is additive on the log-odds scale". Our measured ratios (×12, ×4.5, ×2.4) already look like design constants.
- **Test.** Poisson or logistic regression of purchase (and click) on ~15 binary indicators plus log(slot weight) and log(appeal), on live feedback. Fit on the first half of the day, then the second half. If coefficients are stable and exp(β) lands near round numbers, the simulator is log-linear and the model is close to its truth. Compare its held-out log-loss with LightGBM (0.00765 on buy).
- **Code.** A strategy `loglin.py` whose score is exp(Σ β_j x_j) with fitted β. Use it alone if it ties LightGBM (it will generalise better to the final's new shoppers and products, because it has no IDs and few parameters), or as a prior feature for LightGBM.

### 3. Co-visitation matrices by event type, as candidates and as a score factor
Build three item-to-item tables from organic history: view→view within a session (we have this, 4.3M pairs), view→cart/buy (bought after viewing), and buy→buy across a shopper's sessions. Use them to pull candidates from the recent views and from today's views on home.
- **Evidence.** [F] Co-visitation counts within a time window, weighted by event type, fed to a GBDT reranker, was the common backbone in OTTO; teams used several matrices (clicks, clicks/carts/orders, buys) ([Fedorov OTTO repo](https://github.com/Fedorov-Artem/kaggle_OTTO), [TDS write-up](https://towardsdatascience.com/building-a-recommender-system-using-machine-learning-2eefba9a692e)). Dressipi 2022 runners-up used item co-occurrence features between candidate and session items ([NVIDIA Dressipi write-up](https://medium.com/nvidia-merlin/building-a-diverse-models-ensemble-for-fashion-session-based-recommendation-for-recsys2022-2419d2182c4c)). [F, ours] Co-view already gives ×4 on clicks inside the session category (08, signal 5).
- **Test.** For live feedback rows not in the recent views, bucket by the new view→buy count from the recent views. If buy rate climbs more steeply than with view→view, add it. Also: share of live purchases whose product was in the top-20 view→buy neighbours of a recent view (candidate recall).
- **Code.** One SQL in `sql/features/` per matrix, cached under `data/`. Candidate source "top-20 neighbours of each recent view and each today view". Feature `covis_buy = log1p(Σ n(v→p))`. New products fall back to phrase + subcategory overlap (they have no co-counts).

### 4. Session intent is set by the first view, not the last
Simulators that model a session usually draw one intent at session start and generate views from it. If so, the first view of the session predicts the purchase subcategory better than the last.
- **Evidence.** [F] RecSim's user state is a latent interest vector that shifts with each consumed item ([RecSim NG](https://arxiv.org/abs/2103.08057)); KuaiSim models request-level response, session leave and cross-session return separately ([KuaiSim](https://arxiv.org/abs/2309.12645)). [F, ours] The first view of the session gets 2.4× more clicks than later views.
- **Test.** In organic `shop.events` sessions with a purchase and 3+ prior views: share where the purchased subcategory equals the first view's, the last view's, the modal view's. Same on live feedback: buy rate for products in the first view's subcategory but not the last's, and the reverse.
- **Code.** Features `same_sub_first`, `same_cat_first`, and `position_in_session` of the matching view. If first beats last, weight session category affinity by first view.

### 5. In the final, use hour 1 to seed state for hour 2
Only the last hour counts. If idea 1's test shows that clicks or carts through our lists persist in shopper state, the first hour is an investment: lists that create carts (not purchases) for returning shoppers raise hour-2 conversion.
- **Evidence.** [F] RecoGym and KuaiSim both carry user state across sessions; KuaiSim has an explicit cross-session retention model ([RecoGym](https://arxiv.org/abs/1808.00720), [KuaiSim](https://arxiv.org/abs/2309.12645)). [F, organisers] "What we sell changes later scores." [I] The same mechanism probably works for carts.
- **Test.** Idea 1's "carted via our list earlier" label. Then: for shoppers who saw us twice today, buy rate on the second visit by whether the first visit produced a cart. Needs ~1 h of data, no new code.
- **Code.** Only if positive: a final-round switch in `arms.toml` that, before minute 60, adds a cart-probability term to the score (model `p(cart | click)` from feedback). Do not do this without the test; it gives up hour-1 score, which costs nothing, but also risks selling products that would have sold in hour 2.

### 6. New products in the final: attribute prior, then fast Thompson sampling
The final has new products. Score them from subcategory, brand and phrases (we do), and give them an exploration bonus in hour 1 so that by hour 2 we know which convert.
- **Evidence.** [F] Thompson sampling is designed for cumulative reward; top-two Thompson sampling is the variant built for identifying the best arm quickly ([Russo 2016](https://arxiv.org/abs/1602.08448)). [F, ours] New products show 6.5% buy-per-view against 5.3% (novelty hypothesis open).
- **Test.** On today's practice catalogue updates: our feedback clicks/buys on products added today versus the attribute-predicted rate. A ratio well above 1 means a novelty boost exists.
- **Code.** For products younger than N minutes, sample their rate from Beta(α0 + buys, β0 + non-buy weighted impressions) with α0/(α0+β0) = attribute prediction and α0+β0 ≈ 50 slot-weighted impressions. Turn sampling off at minute 60.

### 7. Rank by expected purchase probability; on home, marginalise over intent; drop diversity heuristics
Sort the final 10 by one calibrated E[p_i]. On home, E[p_i] = Σ_c P(intent = c | shopper) × p(i | c). Do not add MMR or forced category spread.
- **Evidence.** [F] Diversity pays when the objective is "at least one relevant item" and relevance probabilities are high: Chen & Karger show greedy "hedging" beats probability ranking for finding at least one relevant result ([Less is more](https://ir.webis.de/anthology/2006.sigirconf_conference-2006.57/)); Radlinski et al. learn diverse rankings to minimise abandonment ([ICML 2008](https://icml.cc/imls/conferences/2008/papers/264.pdf)). [I] Both regimes have p near 0.3–1. At p ≈ 0.01–0.05 the concavity of 1 − Π(1 − p) is tiny, and an expected value is linear in each p_i, so hedging adds nothing beyond using the right marginal. Correlated p_i (same category) matter only through the pair term, which is a few % of the total.
- **Test.** On live feedback, regress per-request purchase on Σ_k w_k p̂_k (our model's prediction) plus number of distinct categories in the list. If the category count coefficient is ~0 at fixed Σ, diversity is irrelevant. Also check calibration: buckets of Σ w_k p̂_k against observed rate.
- **Code.** Remove any hard caps on items per category. Compute home intent probabilities from the shopper's category rank (1 / 0.3 / 0.1 already measured) and segment, and multiply.

### 8. Gate personal history by the shopper's cart propensity; new shoppers get segment best sellers plus today's views
How much to trust a shopper's own history is itself a shopper feature.
- **Evidence.** [F, ours] Strongest interaction found: carted-not-bought × shopper cart rate (H² 0.17). New shoppers: all purchases on the top-14 best sellers, and today's views ×3 on subcategory. [F] Contextual cold start in RecoGym-like simulators shares one latent user vector between organic views and recommendation responses, so organic views today are the cheapest signal for a cold user ([RecoGym](https://arxiv.org/abs/1808.00720)).
- **Test.** Home requests of returning shoppers, split by quintile of `u_cpv`: buy rate of carts shown vs best sellers shown. Expect the cart lift to vanish in the bottom quintile.
- **Code.** In `cold2`, multiply the cart bonus by a function of `u_cpv`; for the bottom quintile fill with segment best sellers instead.

### 9. Make a small slice of traffic stochastic with logged propensities, then evaluate challengers offline
Our deterministic arms cannot be compared offline: a new ranker shows products we never showed. A 5% stochastic arm with known propensities fixes that.
- **Evidence.** [F] IPS-type estimators need the logging policy to cover the target policy's actions; the slate pseudo-inverse estimator assumes the slate reward is additive over slots and gives exponential savings over whole-slate IPS ([Swaminathan et al.](https://arxiv.org/abs/1605.04812)); cascade DR reduces variance further when users scan top-down ([Kiyohara et al.](https://arxiv.org/abs/2202.01562)). [F, ours] Slots look independent, so the additive assumption holds approximately.
- **Test.** None needed before building; after 2 h of the stochastic arm, check the effective sample size (below).
- **Code.** Arm `pl_explore`: score the champion's top-30, sample a 10-list by Plackett–Luce (Gumbel-top-k on score/τ). Log for each shown item its slot propensity π0(item at slot k | x), estimated by 300 Monte-Carlo resamples per request (cheap). See "Faster evaluation".

### 10. Final protocol: no exploration in the scored hour, one champion–challenger alternation in hour 1
- **Evidence.** [F, ours] Leaderboard blocks have a floor of about 1 score point per 10-minute block (PLAN §7). [F] Sequential elimination and top-two sampling identify the best of k arms with fewest samples ([Russo 2016](https://arxiv.org/abs/1602.08448)). [I] With 6 blocks in hour 1, alternating two arms gives 3 blocks each: SE of the difference ≈ 1 × √(2/3) ≈ 0.8 points, so a ≥2-point gap is visible. Three or more arms leave 2 blocks each and nothing is visible. Thompson sampling across strategies adds no power at this scale.
- **Test.** Rehearse in Sunday practice: two arms alternating for one hour, decide at minute 60 by a pre-written rule.
- **Code.** A block schedule in `arms.toml` for the final: hour 1 alternates champion / challenger, hour 2 is the winner (challenger only if ahead by ≥ 2 points, else champion). Turn off explore and Thompson bonuses at minute 60. Check first that the leaderboard refreshes during the final; if not, champion only.

## How simulators like this are usually built

**[F]** What each reference simulator models, from its paper or code:

| Simulator | User side | Item side | Response | Source |
|---|---|---|---|---|
| RecSim (Google) | latent interest vector, time budget, satisfaction | latent quality, topic, observable features | choice model over the slate (multinomial logit or cascade-like); interest drifts toward consumed topics | [arXiv 1909.04847](https://arxiv.org/abs/1909.04847), [RecSim NG 2103.08057](https://arxiv.org/abs/2103.08057) |
| RecoGym (Criteo) | latent user embedding shared by organic browsing and ad response | item embeddings | organic sessions and bandit sessions alternate; a parameter sets how much organic and bandit behaviour differ | [arXiv 1808.00720](https://arxiv.org/abs/1808.00720) |
| Open Bandit Pipeline synthetic slate | context vector | action features | base reward per (context, action), position effect (1/k)^η, structures `independent`, `standard_additive`, `cascade_additive`, `*_decay`; click models `pbm`, `cascade` | [obp code](https://raw.githubusercontent.com/st-tech/zr-obp/master/obp/dataset/synthetic_slate.py), [OBP paper](https://arxiv.org/abs/2008.07146) |
| KuaiSim | user state from history | video features | immediate response model, leave model, cross-session retention model | [arXiv 2309.12645](https://arxiv.org/abs/2309.12645) |
| Virtual-Taobao | customers generated by GAN-SD | items as features | customer policy learned by adversarial imitation from real logs | [arXiv 1805.10000](https://arxiv.org/abs/1805.10000) |
| RL4RS, MARS-Gym | logged-data simulators for list and marketplace recommendation | | not fetched; listed as baselines in KuaiSim | KuaiSim paper |

**[I]** An AI agent writing a shop simulator in a day would most likely produce: shopper = segment (device × region) + category taste vector + phrase taste + price sensitivity; session = one intent category/subcategory drawn at start; views generated from intent; list response = position weight × click probability from a logistic or multiplicative utility, at most one click, then buy-after-click; a bought set that suppresses rebuy; catalogue events (new products, price cuts, trends) as multipliers on a subcategory. Our measurements fit this picture on every row we have tested.

### Observable signatures, and the SQL that tests each

| Latent component | Signature in the data | Test on our tables | Status |
|---|---|---|---|
| Position bias, PBM | same product, CTR across slots ∝ fixed curve, independent of neighbours | CTR of one product by slot; ratio slot k / slot 1 | confirmed 1/log2(k+1) |
| Cascade (scan, stop at click) | strong slot above lowers clicks below | clicks at slots 2–10 by whether slot 1 had a high-p item, within shopper type | not seen (3.99% vs 2.80%) → PBM, not cascade |
| Multinomial choice with outside option | adding a strong item lowers others' click share | same as above, plus total clicks per list sublinear in Σ p | at most one click observed; test sublinearity |
| Session intent drawn at start | first view predicts purchase better than last; views in a session cluster in one subcategory | idea 4 query | partly (first view ×2.4; 73% same subcategory next view) |
| Interest drift (RecSim) | later views in a session move toward items viewed, not back to first | Markov transition of subcategory within session vs to first view | open |
| Long-term taste vector | per-shopper shares of category, phrase, brand predict response | done in 08 | confirmed (phrase share strongest) |
| Item latent quality | product-level residual after attributes, stable across days | residual of buy-per-view by product, split halves, correlation | partly (attributes explain ~half) |
| Price sensitivity per segment | price coefficient differs by segment | logistic on price z-score × segment | weak overall; segment split open |
| Popularity term | conversion rises with log popularity at fixed attributes | bucket by log views at fixed subcategory | history yes, live weak (carousel CTR ×1.1) |
| Novelty / fatigue | new products over-perform; products shown repeatedly to one shopper decay | conversion by number of prior impressions of that product to that shopper in our feedback | novelty open; fatigue untested — cheap query |
| Funnel | buy only after click, buy-after-click depends on slot | done | confirmed |
| Organic vs recommendation differ (RecoGym "flips") | an effect with opposite sign in history and live | done for rebuy | confirmed for rebuy only |
| Feedback writes state | our carts/clicks change later response | idea 1 query | open, important for the final |

The fatigue test is worth 10 minutes: count, for each live impression, how many times we showed the same product to the same shopper earlier today, and bucket buy rate by 0, 1, 2, 3+. If it decays, stop re-showing a product after two misses.

## Faster evaluation

### What we have
About 3,000 clicks and 900 purchases on our own lists, almost all from deterministic arms, a 2% explore arm, and leaderboard blocks that give the expected conversion (a probability, not coin flips) per 10 minutes.

### Estimators (formulas) [F: definitions; I: what to trust]
Notation: request x_i, logged list A_i, slot weights w_k, logging policy π0, target policy πe, purchase r.

- **IPS (whole list):** V̂ = (1/n) Σ_i r_i · πe(A_i|x_i) / π0(A_i|x_i). Useless for 10-item lists: the ratio is almost always 0.
- **SNIPS:** V̂ = Σ_i ρ_i r_i / Σ_i ρ_i, ρ_i the importance ratio. Same support problem, lower variance.
- **Item-position IPS (pseudo-inverse under additivity / PBM):** V̂ = (1/n) Σ_i Σ_k r_{i,k} · πe(a_{i,k} at k | x_i) / π0(a_{i,k} at k | x_i), with r_{i,k} the purchase at slot k. Unbiased if the list value is the sum of slot values ([PI estimator](https://arxiv.org/abs/1605.04812)). When πe is deterministic, πe(a at k) is 1 or 0, so only slots where the logged item equals the challenger's item at that slot count. A softer and still valid version uses "item anywhere in the challenger's top 10, reweighted by the slot curve": V̂ = (1/n) Σ_i Σ_k r_{i,k} · (w_{k'}/w_k) · 1[a_{i,k} at slot k' in πe] / π0(a_{i,k} at k | x_i), valid under PBM because the slot effect is known.
- **Doubly robust:** V̂ = (1/n) Σ_i [ q̂(x_i, πe) + Σ_k ρ_{i,k} (r_{i,k} − q̂(x_i, a_{i,k}, k)) ], q̂ our click × buy model. It keeps the model's low variance and corrects its bias where support exists ([DR, Dudík et al.](https://arxiv.org/abs/1103.4601), not fetched). Cascade DR is the version for top-down scanning ([Kiyohara et al.](https://arxiv.org/abs/2202.01562)); we measured PBM, so plain slot-wise DR is the right one.
- **Direct method:** V̂ = (1/n) Σ_i Σ_k w_k p̂(πe's item at k | x_i). Low variance, biased toward whatever our model believes, and biased in favour of any challenger built from the same model.

### How reliable with our volumes [I]
- Effective sample size n_eff = (Σ ρ)² / Σ ρ². Relative standard error of an IPS estimate ≈ 1 / √(purchases × n_eff/n).
- With 900 purchases and n_eff/n = 1 (on-policy), relative SE ≈ 3.3%: on a 1.6% rate that is ±0.05 points, about 2 score points. With a stochastic arm of 5% traffic over 4 h (~2,200 requests, ~35 purchases) and n_eff/n ≈ 0.3, relative SE ≈ 30%: only large differences show.
- So: **use DR with our click × buy model as q̂, on the stochastic arm's data, to filter challengers; trust the leaderboard blocks to decide.** Self-normalise the slot ratios (wPI, reported better than PI in the original paper, per [control variates paper](https://arxiv.org/abs/2106.07914)) and clip ratios at 20.
- The 2% explore arm: if it is uniform random over the candidates, per-slot replay works ([Li et al. replay](https://arxiv.org/abs/1003.5956), not fetched), but with 2% traffic it yields a handful of purchases per hour. Better to change it to Plackett–Luce around the champion (idea 9): the same exploration cost lands on products the challenger would actually show.
- Leaderboard blocks already measure expected conversion, removing coin-flip noise. They remain the best evaluator we have; the offline estimators only decide what earns a block.

## Notes on competitions [F unless marked]
- OTTO (Kaggle 2023, session clicks/carts/orders): two-stage, candidates from session history plus several co-visitation matrices (time-windowed, weighted by event type), then GBDT rankers per target; word2vec and BPR as extra candidate sources in some solutions ([OTTO blog](https://www.otto.de/jobs/en/blogs/techblog/otto-machine-learning-competition/), [Fedorov](https://github.com/Fedorov-Artem/kaggle_OTTO), [NVIDIA](https://github.com/bschifferer/Kaggle-Otto-Comp)).
- H&M (Kaggle 2022): several retrieval strategies including repurchase, then rankers; negative downsampling was necessary ([summary](https://goldandrabbit.github.io/2022/05/15/H&M%20Recommendation%20Competition%20Top1%20%E6%96%B9%E6%A1%88)).
- RecSys 2019 Trivago: won by LogicAI with an ensemble over 25,000 hand-made features; second and fourth places used feature engineering with tree boosting ([arXiv 2010.06987](https://arxiv.org/abs/2010.06987), [announcement](https://www.globenewswire.com/news-release/2019/10/10/1928207/0/en/recsys-challenge-2019-winners-announced.html)).
- RecSys 2022 Dressipi: predict the purchase ending a session; top teams combined item co-occurrence with session items, item attributes, and ensembles ([challenge](https://recsys.acm.org/recsys22/challenge/), [NVIDIA](https://medium.com/nvidia-merlin/building-a-diverse-models-ensemble-for-fashion-session-based-recommendation-for-recsys2022-2419d2182c4c)).
- Two-stage candidate generator + reranker formalised in [arXiv 1908.08284](https://arxiv.org/abs/1908.08284).
- [I] Common thread: what moved scores most was candidate recall from the session and repeat items, then co-visitation, then a GBDT ranker with session × item features. Embeddings (item2vec, session transformers) helped at the margin in large real catalogues. Our neural model found no latent structure beyond explicit attributes (08), so embeddings are a low priority for a synthetic catalogue.

## Not worth our time [I]
- MMR / DPP diversity re-ranking (see the opening section).
- item2vec or session transformers: 3,000 clicks, synthetic attributes, no hidden clusters found.
- Live trend lists for cold shoppers: all-time list already ties them (H-home-ceiling Q3).
- Multi-arm Thompson sampling across strategies in the final: not enough blocks.

## Sources
Fetched or seen in search results:
- RecSim: https://arxiv.org/abs/1909.04847 · RecSim NG: https://arxiv.org/abs/2103.08057
- RecoGym: https://arxiv.org/abs/1808.00720
- Open Bandit Pipeline: https://arxiv.org/abs/2008.07146 · slate generator code: https://raw.githubusercontent.com/st-tech/zr-obp/master/obp/dataset/synthetic_slate.py
- KuaiSim: https://arxiv.org/abs/2309.12645
- Virtual-Taobao: https://arxiv.org/abs/1805.10000
- Slate off-policy evaluation (pseudo-inverse): https://arxiv.org/abs/1605.04812
- Control variates for slate OPE: https://arxiv.org/abs/2106.07914
- Cascade doubly robust: https://arxiv.org/abs/2202.01562
- Learning diverse rankings with bandits: https://icml.cc/imls/conferences/2008/papers/264.pdf
- Less is more (at least one relevant): https://ir.webis.de/anthology/2006.sigirconf_conference-2006.57/
- Top-two Thompson sampling: https://arxiv.org/abs/1602.08448
- OTTO: https://www.otto.de/jobs/en/blogs/techblog/otto-machine-learning-competition/ · https://github.com/Fedorov-Artem/kaggle_OTTO · https://github.com/bschifferer/Kaggle-Otto-Comp · https://towardsdatascience.com/building-a-recommender-system-using-machine-learning-2eefba9a692e
- H&M top 1 summary: https://goldandrabbit.github.io/2022/05/15/H&M%20Recommendation%20Competition%20Top1%20%E6%96%B9%E6%A1%88
- Trivago 2019: https://arxiv.org/abs/2010.06987 · https://www.globenewswire.com/news-release/2019/10/10/1928207/0/en/recsys-challenge-2019-winners-announced.html
- Dressipi 2022: https://recsys.acm.org/recsys22/challenge/ · https://medium.com/nvidia-merlin/building-a-diverse-models-ensemble-for-fashion-session-based-recommendation-for-recsys2022-2419d2182c4c
- Two-stage session recommendation: https://arxiv.org/abs/1908.08284

Cited from memory, not fetched this session (check before quoting): doubly robust policy evaluation, Dudík et al. 2011, https://arxiv.org/abs/1103.4601 · replay evaluation, Li et al. 2011, https://arxiv.org/abs/1003.5956 · SNIPS, Swaminathan & Joachims, NeurIPS 2015 · cascade click model, Craswell et al., WSDM 2008 · MMR, Carbonell & Goldstein, SIGIR 1998.
