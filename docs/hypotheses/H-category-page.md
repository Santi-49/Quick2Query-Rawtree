# H-category-page · the category being browsed is not the last view's category
- **status**: rejected for the page, confirmed for every page. Category pages do not under-convert under rules2 once the session has views; when the views' main category differs from the last view's, the main category wins.
- **owner**: agent
- **claim**: on category pages the browsed category is often not the category of the last recent view, so rules2's "same category as the last view" misses; the majority category of the views predicts better.
- **test**: `sql/hypotheses/H-category-page.sql`, run 14 Nov 16:20 UTC on all live feedback since 10:58 (every strategy pooled unless named; impressions weighted 1/log2(slot+1); ctr_w, conv_w = clicks, buys per 100 weighted impressions). Majority = category with most views, strictly more than the last view's. History: 1.6M carousel requests with views.

## 1 · Premise, live per request with recent views
| strategy | category: requests / clicks / buys / conv | product: requests / clicks / buys / conv |
|---|---|---|
| rules2 | 2,571 / 135 / 52 / 2.02% | 6,310 / 320 / 117 / 1.85% |
| jasper | 415 / 23 / 10 / 2.41% | 942 / 29 / 11 / 1.17% |
| rules (v1) | 1,472 / 52 / 17 / 1.15% | 3,447 / 149 / 50 / 1.45% |
| best sellers | 4,029 / 124 / 34 / 0.84% | 9,241 / 240 / 93 / 1.01% |
- The session looks the same on both pages: 2.6 views, 1.3 categories, 1.4 subcategories, majority ≠ last in 8–10% of requests. Half-hour windows of rules2 swing 1.2–3.5% on category pages (10–15 buys each), so the 0.6–0.7% reading was noise or `rules` v1, not a lasting gap.

## 2 · History, per request: the carousel's single category against the views (it is always the last view's)
| page | views | shown category | requests | clicks | buys | conv |
|---|---|---|---|---|---|---|
| category | one category | = last = majority | 357,602 | 17,810 | 6,995 | 1.96% |
| category | mixed | = last = majority | 80,541 | 2,705 | 875 | 1.09% |
| category | mixed | = last, not majority | 42,043 | 1,055 | 340 | 0.81% |
| product | mixed | = last = majority | 188,849 | 6,406 | 2,075 | 1.10% |
| product | mixed | = last, not majority | 97,498 | 2,431 | 696 | 0.71% |
A last-view category that is not the majority converts ×0.74 (category page) and ×0.65 (product page). The carousel never showed the majority category when it differed, so history cannot score it directly.

## 3 · Live impressions on requests where the majority category ≠ the last view's
| shown product | category page: w / clicks / buys / ctr_w | product page: w / clicks / buys / ctr_w | pooled ctr_w, conv_w |
|---|---|---|---|
| a recent view | 526 / 4 / 3 / 0.76 | 1,313 / 9 / 3 / 0.69 | 0.71, 0.33 |
| last view's category | 1,235 / 6 / 2 / 0.49 | 3,046 / 23 / 5 / 0.76 | 0.68, 0.16 |
| majority category | 1,005 / 10 / 5 / 1.00 | 2,242 / 25 / 10 / 1.12 | **1.08, 0.46** |
| other category | 3,489 / 13 / 0 / 0.37 | 8,127 / 31 / 8 / 0.38 | 0.38, 0.07 |
- Majority over last view's category: ×1.6 clicks (35 against 29), ×2.8 buys (15 against 7). Same direction on both pages. 68% range on clicks ×1.2–2.1.
- Subcategory, same cut (`4`): majority subcategory 12 clicks, ctr_w 1.13; last view's subcategory 17 clicks, 1.10. No difference: keep the subcategory on the last view.
- Next organic view within 10 min (`5`): same subcategory or category as the last view 3.8% on category pages, 3.7% on product pages; none 81.6% / 82.3%. Recent views are not in `shop.events`, so this is another session and cannot tell the browsed category.

## verdict
- No page effect: do not build a category-page special case. **The session's main category is the one with most views**, ties to the earliest view (`H-reshow-rank`: the first view is the anchor), and it should carry the category weight that rules2 gives to the last view: ×1.6 clicks, ×2.8 buys when they differ, which is 9% of requests.
- Effect on the whole traffic is small: 9% of requests × a few slots.

## next
- rules4 (CATEGORY_MAIN 4.5, CATEGORY_OTHER 3.0). Re-read section 3 on rules4 lists after 2 h: the majority cell needs ~60 clicks for a ±25% range.
