# 08 · ML pattern mining: many aggregates at once, what the models find

Run 14 Nov 17:00–18:10 UTC. Scripts: `eda/ml/` (`pulls.py`, `build.py`, `gbm.py`, `nn.py`, `segments.py`). Re-run queries: `sql/hypotheses/H-ml-signals.sql`. Hypothesis: `docs/hypotheses/H-ml-signals.md`. Caches and raw outputs (`gbm_out.txt`, `importance_*.csv`, `nn_out.txt`, `seg_out.txt`) are in `data/ml/`.

## What was fed in

| | Live | History sample |
|---|---|---|
| Rows (one per shown product) | 642,080 (64,208 feedback requests, 09:00–16:02) | 669,550 (66,955 carousel requests, 4–14 Nov, shoppers with `cityHash64(user) % 5 = 0`) |
| Clicks / purchases | 1,895 / 600 | 2,573 / 1,030 |
| Shopper and product aggregates from | all organic history (< 14 Nov 07:00) | organic history before 4 Nov 07:00, so no leakage |
| Features | 188 | 181 (no live store state) |

| Group (prefix) | n | Examples |
|---|---|---|
| slot, context | 11 | slot, 1/log2(slot+1), page, device, region, hour, new shopper, segment lift, android-south |
| session `s_` + ranker session features | 33 | number, span and age of the recent views; position of the product in them; same subcategory/category/brand/price band/phrases as the last view and as any view; price against the views' mean; one-subcategory session; organic co-view counts from the views to the product |
| product `p_`, group `g_` | 61 | views, carts, buys, per-view rates, viewers, 7-day trend, price rank and z-score in subcategory/brand/category, age, the 20 phrase flags, attribute-predicted appeal and residual, carousel CTR/CVR, brand/subcategory/category aggregates |
| shopper `u_` | 32 | views, carts, buys, distinct products, repeat-buy rate, cart per view, sessions, active days, session length/duration, share of sessions with a cart/purchase, entropy and count of categories/subcategories/brands, hour habits, weekend share, price-percentile preference |
| shopper × product `x_` | 44 | views/carts/buys of the product, carted-not-bought, days since; views, carts, buys, share, rank, days since for its category, subcategory, brand and price band; share of history views carrying its phrases; price against the shopper's preference |
| live store state `l_` | 7 | minutes since price/stock change, price ratio, views of the product and subcategory in the last 15 min, against 2 h |

## Model scores (newest 20% of requests held out; fit on the oldest 70%, early stopping on the next 10%)

| Rows | Label | Wide (all features) | 21 ranker features | Wide without `l_` |
|---|---|---|---|---|
| live → live | click (521 test clicks) | **AUC 0.821**, log-loss 0.02279 | 0.777, 0.02382 | 0.823 |
| live → live | buy (169 test buys) | **0.909**, 0.00765 | 0.872, 0.00833 | 0.913 |
| history → history | click (515) | 0.897, 0.01924 | 0.860, 0.02087 | |
| history → history | buy (197) | 0.973, 0.00658 | 0.931, 0.00799 | |
| history model → live test | click | 0.787, 0.02699 | 0.746, 0.02619 | |
| history model → live test | buy | **0.643**, 0.01060 | 0.773, 0.00924 | |
| slot alone, live click | | 0.709 | | |

- The wide set adds +0.045 AUC on live clicks and +0.037 on live purchases over the ranker's 21 features. The 7 live-state features add nothing (removing them is +0.002).
- The neural model (below) gets 0.814 on live clicks: **it does not beat LightGBM.**
- The history click model transfers in part (0.787 on live). The history purchase model does not (0.643, worse than its own 21-feature version), because it learnt "bought before" and repeat buying (see the last section).
- Caveat: AUC here is across all impressions, so shopper-level features (which cannot reorder one list) also earn credit. The "how to use" column below says which signals can reorder a list.

## Ranked new signals (live click model; permutation = AUC drop on the held-out live rows, mean of 2 shuffles)

Effects are per 100 impressions weighted 1/log2(slot+1) (`click_pw`, `buy_pw`), on live rows. "Known" = already in `docs/SIMULATOR.md` or the 21 ranker features.

| # | Signal | Group | Perm. click / buy | Effect on live, with counts | Needs known shopper / product? | Known? | How to use it |
|---|---|---|---|---|---|---|---|
| 1 | **Phrase taste** `x_ph_share`: share of the shopper's history views carrying each of the product's 2 phrases, summed (median ≈0.2) | shopper × product attribute | **0.023 / 0.021** (largest of all 188) | Products the shopper never viewed: ≤0.22 → 0.13 / 0.020 (80 clicks, 13 buys); 0.22–0.30 → 0.37 / 0.08; 0.30–0.38 → 0.89 / 0.21; >0.38 → **2.11 / 0.94** (141 clicks, 63 buys). Holds inside every category-share bucket (cat share >0.35: 0.93 → 7.1 clicks) and inside subcategory share | shopper yes; product no (phrases come from the description, so new products too) | no (phrase-affinity was open) | multiply candidate score by a phrase-taste factor; pull non-viewed products with the shopper's phrases into the candidates, also from other categories |
| 2 | **Session phrase overlap** `s_ph_overlap_sum`: matches between the product's phrases and the recent views' phrases | session | 0.009 / **0.015** | Shown product not in the views. Other category: 0 → 0.27 / 0.043 (241 clicks); 1 → 0.65 / 0.18; 3+ → 1.30 / 0.49 (74). Same category as the last view: 0.81 → 2.12. Same subcategory: 0.77 → 4.6 at 3+ (19 clicks) | no: works for new shoppers and new products | no | inside the session category, prefer products sharing the viewed products' phrases; for cross-category fill, choose by phrase overlap |
| 3 | **Shopper cart propensity** `u_cpv` (carts per view), `u_sess_cart_rate` (share of sessions with a cart) | shopper | 0.008 / 0.009; 0.002 / 0.003 | Bottom fifth of `u_cpv` 0.13 / 0.010, top 2% 2.58 / 1.40 | shopper yes | no | does not reorder a list alone; it scales the history signals (interaction 1) and tells how much to trust a shopper's own history over best sellers |
| 4 | **Carts in the category** `x_cat_c` | shopper × category | 0.006 / 0.0006 | 0 carts 0.15 / 0.023 (150 clicks); 4–12 → 0.87 / 0.22; 13–29 → 1.26 / 0.34 | shopper yes | partly (category share is known; carts add to views) | use carts next to the views share when ranking categories for a shopper |
| 5 | **Organic co-view** `s_coview_any`: count of consecutive organic views v → product, summed over the recent views | session × product | 0.0045 / 0.0021 | Same category as the last view: 0 → 0.55 / 0.15 (43 clicks); 5–20 → 1.46 / 0.55; 21+ → 2.40 / 1.20 (82). Other category: 0.31 → 1.38 (62) | product yes (new products have no co-views) | no | item-to-item candidates and a score factor; for new products fall back to phrase overlap |
| 6 | **Carted, not bought** `x_p_cart_nobuy` (history) | shopper × product | 0.0043 / 0.0019 | Carted 2.54 / 0.83 (421 clicks, 138 buys) against viewed only 0.51 / 0.074 (263, 38) and never 0.38 / 0.10. Twice or more: product page 3.9 / 1.19, home 3.3 / 0.84 | both | no. "Viewed before" in the ranker is mostly this: viewed-only is barely above never | replace the flat viewed-before bonus by a carted-not-bought bonus; on home this is the best personal candidate |
| 7 | **Last view's category** `s_last_cat` (as category) | session | 0.0024 / 0.0016 | Last view in Electronics or Books (one PD bin): 0.99 / 0.38 on everything shown, against 0.41–0.71 for the other bins (Toys bin mixed with home requests) | no | partly (category rates are known) | a request-level prior; no reordering |
| 8 | **Phrase purchases** `x_ph_buys` | shopper × product attribute | 0.0019 / – | 0–2 → 0.25 / 0.05; 12+ → 1.1–1.3 / 0.34–0.39 | shopper yes | no | weaker twin of 1 |
| 9 | **Appeal of the last viewed product** `s_last_appeal`, `s_last_bpv` | session | 0.0017 / 0.0029 | Bottom fifth 0.47 / 0.13, top 2% 1.68 / 0.96 | last product yes (appeal) | no | request-level; interacts with phrase overlap (interaction 3) |
| 10 | **Subcategory share** `x_sub_share` | shopper × subcategory | 0.0012 / – | <1% 0.20 / 0.05; >15% 2.17 / 0.86 | shopper yes | partly (history only) | next to category share |
| 11 | Co-view share of the last view `s_coview_last_share` | session × product | 0.0010 / – | 0 → 0.46; >1.2% → 1.45 / 0.50 | product yes | no | variant of 5 |
| 12 | Number of subcategories browsed `u_n_sub` (negative) | shopper | 0.0009 / 0.0004 | ≤29 → 0.95 / 0.37; 64+ → 0.13–0.35 / 0.02–0.06 | shopper yes | no | broad browsers rarely buy; shopper-level |
| 13 | Carousel CTR of the product `p_car_ctr` | product | – / 0.0016 | top decile against bottom quartile ×1.1 clicks live (×13.5 in history) | product yes | no | weak live; do not trust the history size |
| 14 | Days since bought `x_p_days_buy` | shopper × product | 0.0012 / 0.0007 | 22,250 bought impressions, 16 clicks, 3 buys in total: **too few** to read a recovery with time | both | bought = known | keep excluding bought products |
| 15 | Hour against the shopper's habit `u_hour_diff`, price vs preference `x_price_pct_diff`, session span | various | ≤0.0006 | flat | | no | nothing usable |

## Top interactions (Friedman H² over the top 25 click features, 300 held-out rows)

| Pair | H² | On live rows |
|---|---|---|
| carted not bought × shopper cart rate | **0.172** | Carted: low-cart shoppers 0.47 clicks (12), high-cart shoppers 3.90 / 1.45 (343 clicks, 128 buys). Not carted: 0.15 and 0.81. The bonus is largest exactly for the shoppers who convert |
| category carts × number of subcategories browsed | 0.029 | category carts count most for focused shoppers |
| last view's appeal × phrase overlap with the last view | 0.028 | phrase overlap pays when the last view was a good product |
| slot × cart per view; cart per view × category share | 0.018, 0.016 | buyer-type shoppers react more to slot 1 and to their favourite category |

Everything else is below 0.015. Most of the structure is additive on the log-odds scale.

## The neural model (second opinion)

MLP 128-64 plus a dot product of a shopper/session tower and a product tower; embeddings for subcategory, brand, phrases, category, last-view category, device, region and page; no user or product IDs; same split. **Held-out live click AUC 0.814 against 0.821 for LightGBM**, val 0.847 at epoch 3, then overfitting. Embeddings show no hidden structure:
- 4 nearest subcategories share the category 10% of the time, which is chance (10 categories). Brands: 15%. The neighbour lists look random (Strollers ~ Running Shoes, Chargers, Pet Beds).
- Phrases group a little by meaning (handmade / built for professionals / extra durability; designed for kids / family-size / travel-ready), but with 1,895 clicks this is noise-level.
- Conclusion: no product clusters or segments beyond what explicit attribute shares already carry.

## Unsupervised shopper segments (`segments.py`)

NMF, 8 components, on 27,343 returning live shoppers' history view shares over category (10), brand (80), phrase (20) and price band (5). In words: each component is one favourite category: Fashion (706 shoppers, with expensive items), Books & Media (4,136), Sports with cheap items (2,884), Toys & Baby (3,427), Pets (2,600), Electronics (3,892), Beauty with cheap items (4,384), Computers & Gaming + Home & Kitchen (5,314). Brand and phrase loadings stay small. Android-south is 8–11% of every component: taste and the device × region segment are independent.

| Known live shoppers, held-out AUC | click | buy |
|---|---|---|
| category share + device + region + page + slot + category | 0.755 | 0.849 |
| + cluster id | 0.760 | 0.848 |
| + component affinity to the shown product | 0.779 | 0.873 |
| + explicit shares (brand, subcategory, phrase, price band) | **0.820** | 0.906 |
| explicit shares + affinities | 0.818 | **0.912** |

**Cluster membership adds almost nothing; explicit per-attribute shares carry it.** Component × category lifts are just "favourite category" (Fashion fans ×2.8 on Fashion, Toys ×2.6, Books ×2.5).

## What does not transfer from history to live (top decile against bottom quartile, known shoppers)

| Signal | History click / buy | Live click / buy |
|---|---|---|
| bought this product before | ×11 / ×23 | **×0.2 / ×0.2** (16 clicks, 3 buys) |
| number of purchases of the product | ×1.7 / ×2.4 | ×1.0 / ×1.0 |
| repeat-buy rate of the shopper | ×4.2 / ×8.8 | ×1.7 / ×1.7 |
| carousel CTR of the product | ×13.5 / ×61 | ×1.1 / ×1.5 |
| viewed before (not bought) | ×1.4 / ×1.0 | ×3.1 / ×2.8, larger live |
| phrase taste, cart rate, category carts, co-view | ×25–36 clicks | ×3–13 clicks: same sign, about half the size in log terms |

The history purchase model leans on the first three rows, which is why it scores 0.643 on live. Use history only for direction, never for size.

## Add these features to the ranker next (exact definitions; history = `shop.history_events` before the request)

1. `phrase_share` = Σ over the product's 2 phrases f of (shopper's history views of products whose description contains f) / (shopper's total history views). NaN for new shoppers. Build per shopper a 20-vector once.
2. `session_phrase_overlap` = Σ over the request's recent views v (excluding the product itself) of |phrases(product) ∩ phrases(v)|, capped at 4.
3. `carted_not_bought` = shopper's history `add_to_cart` events for the product if the shopper never bought it, else 0, capped at 3. Replaces `viewed_before` (keep the views as a separate weak feature).
4. `coview` = log1p(Σ over recent views v of n(v → product)), n = number of times product directly followed v in an organic history session (`lagInFrame` over `session_id` ordered by `ts`, views only; 4.3M pairs). 0 for new products.
5. `shopper_cart_rate` = share of the shopper's history sessions with at least one `add_to_cart` (and `cart_per_view` = carts / views). It works through its interaction with 3, so a tree model is needed.
6. `cat_carts` = log1p(the shopper's history `add_to_cart` count in the product's category).
7. `brand_share` and `sub_share` = shopper's history view share in the product's brand and in its subcategory.
8. Optional: `last_view_appeal` = the ranker's `appeal` of the last recent view (request-level, helps calibration).

## Time and memory

Pulls 2.5 min the first time (`up_l`, 6.1M shopper-product rows, takes 57 s), then cached; `build.py` 38 s; `gbm.py` 28 min (permutation importance is 25 of them; 1.05 GB peak); `nn.py` 1 min; `segments.py` 2 min. The tables take about 0.5 GB each in memory. All at 4 threads.
