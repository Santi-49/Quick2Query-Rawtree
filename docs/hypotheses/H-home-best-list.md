# H-home-best-list · which impression classes a home list should be built from (history)
- **status**: answered in history; the "viewed not bought" class is mostly carts (see `H-home-ceiling.md`).
- **owner**: agent
- **claim**: on history home requests, viewed-not-bought products and top-subcategory best sellers beat category best sellers.
- **test**: `sql/hypotheses/H-home-best-list.sql`, run 14 Nov ~16:20 UTC. Home requests from 15 Oct (2M impressions), profile and best-seller ranks from events before.

## result
| class | Σw | clicks | buys | wconv % |
|---|---|---|---|---|
| bought before (history only, zero live) | 16,745 | 429 | 165 | 0.985 |
| viewed not bought, top 3 views in its category | 15,689 | 99 | 23 | 0.147 |
| viewed not bought, rank 4+ | 55,402 | 205 | 35 | 0.063 |
| top subcategory, category best seller 1–30 | 80,749 | 136 | 19 | 0.024 |
| category best seller 1–10 | 385,134 | 507 | 56 | 0.015 |
| best seller 11–30 / other | 335,703 | 175 | 10 | 0.002–0.004 |

- By category rank × class (wconv): top category: viewed 0.172 (33 buys), best seller 1–10 0.088 (29), other 0.023; categories 2–3: 0.063, 0.027, 0.004; others: 0.035, 0.007, 0.001.
- Coverage: 85% of home requests show a category where the shopper has viewed-not-bought products (48% with 10+). Per shopper: median 94 viewed-not-bought products, 30 in the top category.
- Split by cart (H-home-ceiling): carted not bought 0.40 (43 buys) vs viewed only 0.020–0.026 (15).

## verdict
Category rank × "viewed not bought" × best-seller rank orders the classes. But the viewed class is carried by carts; viewed-only products are ×2 over never-seen in history and ×1.7 live.

## next
Built into cold2 (carts first, viewed ×1.5).
