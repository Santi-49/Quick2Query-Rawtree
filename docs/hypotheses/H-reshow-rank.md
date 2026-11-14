# H-reshow-rank · which recent view should lead
- **status**: confirmed, with a different answer from the claim: the **first** (oldest) recent view leads, not the last. It beats later views ×2.4 in clicks at equal popularity, live and in history.
- **owner**: agent
- **claim**: among re-shown recent views, the last one converts best; repeats, price or popularity might rank them better.
- **test**: `sql/hypotheses/H-reshow-rank.sql` plus the 2×2 below (ad hoc, same joins), run 14 Nov 16:25 UTC. Only impressions of a shown product that is one of the request's recent views. All live feedback, every strategy pooled; weighted 1/log2(slot+1); ctr_w, conv_w per 100 weighted impressions. Popularity = history purchases of the product.

## 1 · Position from the end, live (history ctr_w in the last column)
| views | position | imps | avg slot | clicks | buys | ctr_w | conv_w | history ctr_w (clicks) |
|---|---|---|---|---|---|---|---|---|
| 1 | last = first | 3,431 | 2.5 | 71 | 48 | 2.70 | 1.82 | 9.79 (2,341) |
| 2 | last | 2,367 | 2.9 | 13 | 6 | 0.78 | 0.36 | 4.56 (461) |
| 2 | 2nd last = first | 2,548 | 3.0 | 44 | 20 | **2.52** | 1.15 | 7.95 (1,182) |
| 3–4 | last | 2,688 | 3.0 | 16 | 4 | 0.88 | 0.22 | 3.29 (422) |
| 3–4 | 2nd last | 2,317 | 3.6 | 11 | 5 | 0.78 | 0.36 | 3.70 (356) |
| 3–4 | 3rd+ last | 3,901 | 3.3 | 42 | 22 | 1.66 | 0.87 | 6.75 (1,159) |
| 5+ | last / 2nd / 3rd+ | 1,056 / 883 / 3,163 | 3.3–3.7 | 4 / 2 / 24 | 1 / 1 / 14 | 0.59 / 0.39 / 1.27 | | 3.06 / 3.63 / 5.31 |
By position from the start (3–6 views): the first view 50 clicks in 2,799 weighted impressions (ctr_w 1.79, 29 buys), every other position 49 in 6,068 (0.81). History: first 7.2–7.5, others 3.0–4.3 for every length.

## 2 · First view against popularity (requests with 2+ distinct views)
| | live: w / clicks / buys / ctr_w / conv_w | history: clicks / ctr_w / conv_w |
|---|---|---|
| first view, most bought of the views | 3,228 / 74 / 42 / 2.29 / 1.30 | 2,517 / 7.88 / 5.12 |
| first view, not most bought | 1,320 / 20 / 7 / 1.52 / 0.53 | 90 / 3.58 / 1.83 |
| later view, most bought | 3,946 / 37 / 15 / 0.94 / 0.38 | 1,592 / 4.04 / 2.41 |
| later view, not most bought | 3,758 / 23 / 8 / 0.61 / 0.21 | 206 / 2.05 / 1.09 |
- At equal popularity the first view wins ×2.4–2.5 in clicks live (×3.4 / ×2.5 in buys), ×1.95–1.75 in history. Popularity adds ×1.5–2 within each row; rules2's appeal already sorts on it.
- Cheapest of the views: 1.67 (88 clicks) against 0.95 (66); it overlaps with popularity and position. Not used.
- Repeated views: 7 clicks in all (`H-session-shape`): no conclusion.
- Last view in a subcategory already viewed: 0.54 (15 clicks) against earlier views 1.50 (90). Last view opening a new subcategory: 1.32 (18) against 1.57 (33).

## verdict
- Slot 1 among the recent views: the first view, then by appeal. The last view is no better than any later view.
- Later views convert at 0.2–0.4 conv_w, about the level of a same-subcategory product (0.5); rules2 values them as high as the first (×12). rules4: FIRST_VIEW 12, OTHER_VIEW 5 (history ratio first/other ≈ 2 gives 6; live ≈ 3–4.5). 55% of all requests have 2+ distinct views.

## next
- Read rules4's slot 1–3 click rate on first views and later views after 2 h; if later views still convert below same-subcategory picks, lower OTHER_VIEW to 4.
