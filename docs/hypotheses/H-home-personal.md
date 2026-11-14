# H-home-personal · the shopper's own history on the home page
- **status**: confirmed for category share/rank and viewed-not-bought (history and live clicks); subcategory and recency history only; bought-before reversed live.
- **owner**: agent
- **claim**: on home requests of returning shoppers, the purchase probability of a shown product rises with the rank/share of its category in the shopper's history, with the product having been viewed and not bought, with its subcategory's rank, and with how recently the category was viewed.
- **test**: `sql/hypotheses/H-home-personal.sql`, run 14 Nov ~14:30 UTC. History: 200,900 home requests from 15 Oct 07:00 (2.01M impressions), profile from organic events before 15 Oct (no leakage); recency queries use all events before each request (ASOF join). Impression weight w = 1/log2(slot+1); rate = purchases (or clicks) / Σw, in %. Live: 5,250 home requests of returning shoppers in `team_01.feedback` (10:07–13:40, 94% best-seller lists), profile = all history.

## result
**(a) Category of the shown product** (history, 30/30)

| share of history views in the category | imps | Σw | clicks | buys | buy % per w | × vs 5–15% | live clicks (buys) | live click× |
|---|---|---|---|---|---|---|---|---|
| 0 (never viewed) | 294,930 | 134,003 | 48 | 5 | 0.0037 | 0.22 | 3 (1) † | |
| < 5% | 545,250 | 247,738 | 111 | 8 | 0.0032 | 0.19 | 6 (0) | 0.46 |
| 5–15% | 710,190 | 322,679 | 437 | 55 | 0.017 | 1 | 17 (3) | 1 |
| 15–30% | 314,900 | 143,077 | 431 | 74 | 0.052 | 3.0 | 21 (0) | 2.1 |
| 30–50% | 104,010 | 47,258 | 298 | 87 | 0.184 | 10.8 | 27 (6), 30%+ pooled | 5.0 |
| 50%+ | 37,510 | 17,043 | 242 | 81 | 0.475 | 28 | | |

By rank (views): top 0.182 (174 buys), 2nd 0.054 (51), 3rd 0.028 (26), 4th+ 0.011 (54), never 0.0037 (5): top = ×17 the 4th+. By rank on purchases: top 0.204, 2nd 0.063, 3rd 0.053, 4th+ 0.044, never bought there 0.0063. Live top-vs-4th+: click ×5.8 (32 vs 17 clicks; history ×7.6), buys 6 vs 2.

**(b) The product itself** (history 30/30; live)

| state | hist buys | hist % per w | × | live clicks / buys | live % per w (buys) | live × |
|---|---|---|---|---|---|---|
| never viewed | 87 | 0.0105 | 1 | 36 / 3 | 0.0175 | 1 |
| viewed 1, not bought | 43 | 0.076 | 7.3 | | | |
| viewed 2, not bought | 12 | 0.114 | 10.9 | 38 / 7 (all counts) | 0.142 | 8.1 (click ×3.7) |
| viewed 3+, not bought † | 3 | 0.06–0.18 | | | | |
| **bought before** | 165 | 0.985 | **94** | **0 / 0** in 3,590 imps (Σw 1,802) | 0 | 0 (3.8 clicks expected at never-seen rate) |

Within the shown category the viewed-not-bought gain is smaller: top category ×3.2 (0.172 vs 0.054 never-seen), categories 2–3 ×4, others ×8.5 (from H-home-best-list).

**(c) Recency** (before each request). Category last viewed 0–1 / 2–7 / 8–30 / 31+ days / never, purchase per request: top category 0.93% (119 buys) / 0.81% (46) / 0.35% (8) / 1 buy; other categories 0.116% (59) / 0.082% (44) / 0.058% (27) / 0.038% (3) / 0.014% (3). Product viewed and not bought: flat in recency (clicks per w 0.42 / 0.40 / 0.34 / 0.38; 57 buys pooled, ×7.3 over never-viewed). Bought-before products decay with recency (1.97 → 0.37), a history-only repeat cycle.

**(d) Subcategory rank inside the category** (30/30): in the top category, top subcategory 0.429 (88 buys), 2nd 0.171 (28), 3rd+ 0.122 (52), never viewed 0.037 (6); in other categories 0.051 (60), 0.024 (20), 0.022 (34), 0.0052 (17). Top sub ≈ ×2.2–3.2 over the 2nd/3rd+, never-viewed sub ≈ ×0.25.

**New shoppers with organic views today** (live, 2,248 home requests): category share ≥ 30% of today's views click ×3 over a category not viewed today (9 vs 14 clicks; buys 2 vs 7, no conclusion).

## verdict
- Category share is the strongest home signal: ×28 from 5–15% to 50%+ in history, steeper than linear; live click gradient ×5 (30%+ vs 5–15%) matches history clicks (×6.2). **Both.** `1 + 10 × share` (×7 at most) is too flat.
- Viewed-not-bought: ×7 overall, ×3–4 inside the same category, not increasing with count or recency. **Both** (live 7 buys, 38 clicks).
- Subcategory rank (×2.5 / ×0.25) and category recency (×2 for ≤ 1 day vs 8–30 days): **history only.**
- Bought-before: ×94 in history, 0 clicks in 3,590 live impressions. **The trap, confirmed: history only, reversed live.**

## next
Arm on home: top 1–2 categories by share, viewed-not-bought first, then top-subcategory best sellers; measure click× per share bucket live. Keep last-view timestamps per (shopper, category) in state to test recency live. Use today's `shop.events` views as profile for new shoppers.
