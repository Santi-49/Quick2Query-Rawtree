# H-live-factors · the multipliers of `rules` against live feedback
- **status**: rejected in part. Session and segment are the right size or close; three multipliers are wrong by 2–10 times.
- **owner**: agent
- **claim**: the multipliers in `rules.py` match live effect sizes.
- **test**: `sql/hypotheses/H-live-factors.sql`, run 14 Nov 13:40 UTC. 38,348 requests from 10:07 to 13:40: 36,032 best-seller lists, 2,247 `rules` (from 13:27), 941 clicks, 298 purchases. Each of the 10 shown products is one impression, weighted 1/log2(slot+1). Rate = clicks or purchases / summed weights (`w`). `×` = purchase rate over the reference cell, `click×` the same for clicks. Ranges are exp(±√(1/n + 1/n_ref)) on purchases. **Fewer than ~20 clicks: no conclusion (marked †).** 94% of the data is the best-seller list, so the products are not chosen per shopper and the cuts show the shopper's side.

## 1 · Session relation (all shoppers, reference = other category)
| cell | imps | w | clicks | buys | click× | × (68%) |
|---|---|---|---|---|---|---|
| last view | 1,873 | 1,345 | 21 | 17 | 3.8 | 11.4 (8.8–14.8) |
| other recent view | 2,288 | 1,311 | 30 | 16 | 5.5 | 11.0 (8.4–14.4) |
| same subcat as last | 10,819 | 4,635 | 56 | 19 | 2.9 | 3.7 (2.9–4.7) |
| same subcat as earlier only † | 3,394 | 1,527 | 19 | 9 | 3.0 | 5.3 (3.8–7.5) |
| same cat as last | 32,233 | 14,708 | 196 | 73 | 3.2 | 4.5 (3.9–5.2) |
| same cat as earlier only | 8,349 | 3,847 | 38 | 16 | 2.4 | 3.8 (2.9–4.9) |
| other category | 249,464 | 112,758 | 466 | 125 | 1 | 1 |
| no recent views | 75,060 | 34,104 | 115 | 23 | 0.82 | 0.61 (0.49–0.77) |

A recent view converts at 81% of its clicks (17 of 21), against 27% for other products. Subcategory is not better than category.

## 2 · History relation (returning shoppers, reference = never seen)
| cell | imps | w | clicks | buys | click× | × (68%) |
|---|---|---|---|---|---|---|
| bought in history † | 18,214 | 9,112 | 14 | 3 | 0.44 | 0.36 (0.20–0.65) |
| bought today, before the request † | 370 | 191 | 0 | 0 | 0 | none expected (0.17 at the reference rate) |
| viewed 3–9, not bought | 8,804 | 4,231 | 48 | 12 | 3.3 | 3.1 (2.3–4.3) |
| viewed 2, not bought | 10,520 | 4,814 | 49 | 8 | 2.9 | 1.8 (1.3–2.7) |
| viewed 1, not bought | 30,248 | 13,806 | 129 | 39 | 2.7 | 3.1 (2.6–3.8) |
| never seen | 200,026 | 89,690 | 313 | 81 | 1 | 1 |
## 3 · Favourite category (returning; share of history views in the shown category; reference = share ≤ 0.1 in the same row group). As large outside the session category as inside it, so not the session effect in disguise; it overlaps with viewed-before, since viewed products sit in favourite categories
| session | share | imps | clicks | buys | click× (68%) | × |
|---|---|---|---|---|---|---|
| no views | ≤0.1 | 29,015 | 16 | 3 | 1 | 1 |
| no views | 0.1–0.3 | 18,109 | 31 | 1 | 3.0 (2.2–4.1) | 0.5 † |
| no views | 0.3–0.6 | 4,845 | 22 | 3 | 7.7 (5.5–10.7) | 5.6 † |
| no views † | 0.6+ | 601 | 5 | 3 | 12.9 (7.8–21.6) | 41 |
| views, other category | ≤0.1 | 110,270 | 71 | 11 | 1 | 1 |
| views, other category | 0.1–0.3 | 54,934 | 145 | 26 | 4.0 (3.5–4.6) | 4.6 |
| views, other category | 0.3–0.6 | 8,910 | 59 | 22 | 9.7 (8.1–11.5) | 23 |
| views, other category † | 0.6+ | 766 | 13 | 6 | 22 (17–30) | 67 |
| views, viewed category | ≤0.1 † | 10,991 | 15 | 3 | 1 | 1 |
| views, viewed category | 0.1–0.3 | 19,444 | 77 | 19 | 2.8 (2.1–3.7) | 3.5 |
| views, viewed category | 0.3–0.6 | 8,702 | 68 | 33 | 5.4 (4.0–7.1) | 13 |
| views, viewed category | 0.6+ | 1,773 | 32 | 13 | 11.3 (8.3–15.5) | 23 |

## 4 · Segment (android in Andalucía/Canarias/Murcia against the rest, same category and shopper type)
| category | new: clicks south/rest | new click× (68%) | returning: clicks south/rest | returning click× (68%) |
|---|---|---|---|---|
| all, pooled (buys 48/107 and 36/107) | 88 / 299 | 2.8 (2.5–3.2), × 4.3 | 105 / 449 | 2.2 (1.9–2.4), × 3.1 |
| Fashion | 21 / 15 | 11.0 (7.8–15.4) | 10 / 24 | 3.4 (2.4–5.0) † |
| Home & Kitchen † | 8 / 7 | 9.0 (5.4–15.1) | 5 / 6 | 7.0 (3.8–12.8) |
| Computers & Gaming | 11 / 19 † | 5.6 (3.8–8.1) | 15 / 43 † | 3.2 (2.4–4.3) |
| Electronics † | 11 / 23 | 4.5 (3.1–6.5) | 6 / 31 | 1.7 (1.1–2.7) |
| Toys & Baby | 18 / 102 | 1.7 (1.3–2.2) | 38 / 154 | 2.3 (1.9–2.7) |
| Books & Media | 16 / 123 | 1.3 (1.0–1.7) | 29 / 176 | 1.6 (1.3–1.9) |
## 5 · Session × history (returning, cells with ≥300 weighted impressions; × to other category / never seen)
| session \ history | never seen: click× / × | viewed 1–2: click× / × | viewed 3+: click× / × | bought in history |
|---|---|---|---|---|
| other category | 1 / 1 (176 clicks) | 2.9 / 4.1 (86 clicks) | 4.3 / 5.9 (22) | 0.28 / 0 (4 clicks, 0 buys) |
| same cat as last | 3.4 / 6.2 (55) | 4.7 / 6.0 (32) | 5.0 / 4.2 (12) | 1.2 / 0 (5 clicks) |
| same subcat as last | 3.2 / 7.6 (15) | 6.9 / 10.2 (17) | 2.2 / 5.5 (2) | – |
| no recent views | 0.74 / 0.31 (36) | 2.6 / 2.3 (29) | 3.1 / 3.5 (9) | 0 / 0 (0 clicks) |

They do not multiply. Inside the session category, a past view adds ×1.4 in clicks (4.7 against 3.4), not ×3. Outside it the past view carries ×3–4 on its own. Whatever is bigger wins, plus a little.

## 6 · Slot curve (click rate per slot over the list mean, divided by 1/log2(slot+1); 1 = attention only)
| slot | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| rules: clicks (2,247 lists) | 28 | 12 | 4 | 9 | 3 | 3 | 4 | 2 | 4 | 1 |
| rules: ratio | 1.82 | 1.23 | 0.52 | 1.36 | 0.50 | 0.55 | 0.78 | 0.41 | 0.86 | 0.22 |
| best sellers: ratio (36,032 lists) | 1.35 | 1.18 | 1.26 | 1.09 | 0.90 | 0.41 | 0.74 | 0.71 | 0.75 | 0.54 |

`rules` puts its best product first: slot 1 holds 16 of its 24 purchases. Below slot 2 the order looks flat, but 68 clicks are too few to tell.

## verdict
| multiplier in rules.py | history-based value used now | live estimate (× purchases) | rough 68% range | recommendation |
|---|---|---|---|---|
| LAST_VIEW | 35 | 11.4 (clicks 3.8) | 8.8–14.8 | lower to 12 |
| RECENT_VIEW | 20 | 11.0 (clicks 5.5) | 8.4–14.4 | 12, same as the last view |
| SUBCATEGORY (last, earlier) | 6, 5 | 3.7, 5.3 † | 2.9–4.7, 3.8–7.5 | 4 and 4: no subcategory bonus over category |
| CATEGORY (last, earlier) | 4, 3 | 4.5, 3.8 | 3.9–5.2, 2.9–4.9 | 4.5 and 3.5: keep |
| bought → 0 | excluded | 0.36 † (3 buys); today: no data | 0.20–0.65 | keep excluded |
| VIEWED_BEFORE 1 / 2 / 3–9 / 10+ | 1.5 / 3 / 6 / 15 | 3.1 / 1.8 / 3.1 / † | 2.6–3.8 / 1.3–2.7 / 2.3–4.3 / – | flat 3 for any count; 1.4 when the product is already in the session category |
| SHARE_SESSION (1 + w·share, with views) | w = 2 (×1.9 at share 0.45) | ×4 / ×9.7 / ×22 at 0.1–0.3 / 0.3–0.6 / 0.6+ (clicks) | 3.5–4.6 / 8.1–11.5 / 17–30 | w ≈ 20 (bucket midpoints 0.2, 0.45, 0.75) |
| SHARE_HOME (no views) | w = 10 (×5.5 at 0.45) | ×3.0 / ×7.7 / ×12.9 † (clicks) | 2.2–4.1 / 5.5–10.7 / 7.8–21.6 | w ≈ 15 |
| segment, android-south × category | history lift, capped at 15 (Home & Kitchen 14, Fashion 7, C&G 5, Electronics 4, Toys 2, Books 1.2) | pooled clicks 2.8 new, 2.2 returning; per category see 4 | see 4 | keep; Toys and Books 1.5–2 are right; lower returning-shopper lifts by about half |

## next
- At ~10,800 requests/h (265 clicks, 84 purchases per hour over all cells), these cells have fewer than 20 clicks: viewed 10+ (1 click in 3.5 h), bought in history (14), share 0.6+ without views (5), Home & Kitchen and Beauty in the segment (5–8), subcat as earlier view (19), viewed 10+ (1 click, 87 weighted impressions), and Beauty, Home & Garden, Pets and Sports in the segment (≤8 clicks per cell). **The rate is the blocker, not time.** `rules` no longer shows bought products, so the bought-in-history and bought-today cells only grow with an explore arm. One showing a bought product at slot 1 in 10% of lists gets about 1.7 clicks/h (0.154% per weighted impression), so 20 clicks take ~12 h.
- Viewed 10+ and share 0.6+ should fill faster under `rules`, which favours them. Re-run after 2 h of `rules` traffic, about 20,000 lists. Re-measure session × history and the slot curve on `rules` lists alone once they have about 300 clicks (~1 h: `rules` now answers ~10,000 lists/h at 3% clicks).
