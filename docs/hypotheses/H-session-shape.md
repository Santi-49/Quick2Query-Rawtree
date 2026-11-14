# H-session-shape · what the whole list of recent views carries
- **status**: confirmed in part. Which view a product is (first or later) and whether the views stay in one category move rates by far more than 30%; repeats, second-to-last view and price direction do not (or too few clicks).
- **owner**: agent
- **claim**: beyond the last view, the shape of the views (repeats, concentration, the second-to-last view, the price direction, the number of views) moves the click or purchase rate of a shown product by more than 30%.
- **test**: `sql/hypotheses/H-session-shape.sql`, run 14 Nov 16:20 UTC, all live feedback, every strategy pooled. Impressions weighted 1/log2(slot+1); ctr_w per 100 weighted impressions (clicks in brackets). History: 1/4 sample of carousel requests.

## 1 · Shape × relation to the last view, live ctr_w (clicks)
| shape (share of impressions) | the last view | an earlier view | subcat of last | cat of last | other | cat / other |
|---|---|---|---|---|---|---|
| one view (24%) | 2.71 (71) | – | 1.24 (67) | 1.25 (203) | 0.50 (260) | ×2.5 |
| 2+ views, one subcategory (25%) | **0.43 (9)** | 1.59 (55) | 1.28 (69) | 1.19 (205) | 0.41 (243) | ×2.9 |
| 2+ views, one category (6%) | 2.14 (12) | 3.06 (37) | 2.76 (33) | 1.66 (71) | 0.37 (46) | ×4.5 |
| 2+ views, several categories (19%) | 0.79 (12) | 0.92 (31) | 0.85 (26) | 0.79 (77) | 0.55 (246) | ×1.4 |
History, same cut: one subcategory, last view 2.19 (57) against earlier view 5.97 (496); several subcategories 4.59 (201) against 5.80 (330). One view: 9.85 (594).

## 2 · Other cuts, live
| cut | cell: ctr_w (clicks) | against | verdict |
|---|---|---|---|
| a recent view seen 2+ times (3.7% of requests have a repeat) | earlier view 3.45 (4), last view 1.82 (3) | seen once: 1.50 (119), 1.53 (101) | † no conclusion |
| subcategory of the 2nd-to-last view only | 1.19 (23) | subcat of last 1.32 (128) | −10%, no |
| category of the 2nd-to-last view only | 1.08 (42) | cat of last 1.12 (337); older view only 0.91 (38) | no |
| subcategory of the first view only (not the last's) | 1.18 (41) | subcat of last only 1.34 (57); history 1.77 against 1.12 | mixed, no change |
| category of the first view only | 0.99 (66), conv_w 0.45 | cat of last only 0.82 (74), conv_w 0.24 | +20% clicks, ×1.9 buys |
| price direction: trading up × dearer than last | 1.10 (35) | trading up × cheaper 1.21 (188); trading down × dearer 1.24 (61) | no cell >30% with a stable sign |
| number of views (1 / 2 / 3–4 / 5+) on the re-shown last view | see `H-reshow-rank` | | the last view weakens with more views |

## 3 · History cart against history view (`7`, non-home pages; ctr_w (clicks), × against never seen in the same row)
| lists | session relation | carted, not bought | viewed, never carted | never seen |
|---|---|---|---|---|
| best sellers (not chosen per shopper) | other category | 2.15 (24), ×5.6; buys ×6.1 (8) | 0.39 (16), ×1.0 | 0.39 (168) |
| best sellers | session category | 3.25 (15), ×1.8 | 0.84 (8), ×0.5 | 1.77 (118) |
| other lists | other category / session category | ×5.1 (109) / ×2.7 (176) | ×1.0 (69) / ×0.6 (117) | 190 / 426 |
The past-view bonus (×3.1 in `H-live-factors`) is all carts: a view without a cart is worth nothing.

## verdict
- **The position of a view matters more than its recency**: in sessions of 2+ views the last view converts like an ordinary same-subcategory product (0.43–0.79), while an earlier view keeps 1.6–3.1. Live and history agree in sign; size ×2–3.7. Handled in `H-reshow-rank`.
- **Scattered sessions weaken the category relation**: same category over other ×1.4 when the views span several categories, ×2.5–4.5 otherwise. rules4 handles the part where the main category is not the last view's (`H-category-page`); a scatter discount is left for later.
- **History carts replace history views**: carted-not-bought ×5.6 clicks outside the session, ×1.8–2.7 inside; viewed-only ×1.0 / ×0.5. rules4: CARTED 6, VIEWED_ONLY 1 (needs `Shopper.carted`; falls back to VIEWED_BEFORE 3).
- Rejected: repeats († 7 clicks), second-to-last view, price direction.

## next
- A scatter discount (relation × 0.6 when the views span 2+ categories) once 50+ clicks sit in the several-categories row under rules4.
