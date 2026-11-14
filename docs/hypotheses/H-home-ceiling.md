# H-home-ceiling · what a shopper with no recent views clicks and buys, and how high home can go
- **status**: confirmed for carts (live, history, all pages); today's views promising (new shoppers, 9 buys); category by rank confirmed in clicks.
- **owner**: agent
- **claim**: home requests convert at 0.4–0.5% because our lists spend slots on products viewed before; the signal is the history cart (carted, not bought), and for new shoppers the all-time best sellers plus what they viewed earlier today.
- **test**: `sql/hypotheses/H-home-ceiling.sql`, run 14 Nov ~16:20 UTC. Live = `team_01.feedback` on requests with no recent views (all are `page = home`): 9,400 returning, 3,900 new-shopper requests. Rates per slot-weighted impression, wconv = buys / Σ 1/log2(slot+1), in %. History = home requests from 15 Oct against events before.

## result
**Q1 · what returning shoppers buy through our home carousel, by relation to their history** (live home; non-home and history as support)

| shown product | live home Σw | clicks | buys | wconv | live other pages wconv (buys) | history home wconv (buys) |
|---|---|---|---|---|---|---|
| bought before | 2,231 | 0 | 0 | 0 | 0.011 (1) | 0.99 (165), the trap |
| carted 2+ times, not bought | 870 | 30 | 8 | **0.92** | 1.06 (29) | 0.40 (43), all carts |
| carted once, not bought | 3,426 | 51 | 8 | **0.23** | 0.84 (87) | |
| viewed, never carted | 13,200 | 43 | 4 | 0.030 | 0.07–0.09 (30) | 0.020–0.026 (15) |
| never touched | 23,001 | 49 | 4 | 0.017 | 0.10 (103) | 0.0105 (87) |

- Carts are 16 of the 24 home purchases of returning shoppers. 96% of returning home requests come from a shopper with a cart-not-bought product (median 9 carted once, 44% have one carted twice). Shown a cart product: 0.50% per request (21 / 4,177); has carts, none shown: 0.04% (2 / 4,913). Every arm shows ~1.9 carts by accident (via "viewed before"); slate-h 1.96, opal-h 1.84.
- "Viewed before" without a cart is ×1.7 at most; cold1's ×4 on any viewed product mostly promotes noise (only 3.5% of once-viewed products were carted, 22% of 3×-viewed).
- Category by rank, products not carted: top 0.078 (2 buys, click 0.90%), 2nd–3rd 0 (click 0.17%), 4th+ 0.007 (1, click 0.11%). Top subcategory (click 0.81 vs 0.96 other sub) and brand seen before (0.18 vs 0.14) show nothing live.
- Device × region (per request): android-south returning 0.77% (7 / 909), new 1.82% (7 / 385); others returning 0.20% (17 / 8,580), new 0.48% (17 / 3,538).
- New shoppers: all 24 purchases and all but 3 of ~69 clicks were on the top-14 all-time best sellers (E-Reader p_adc3e6 alone: 8 buys).
- **Today's views** (organic, earlier sessions): 88% of returning and 91% of new home requests have them. New shoppers: product viewed today 0.96 (2 buys, 6 clicks, Σw 209), its subcategory 0.42 (7), category only 0.13 (6), other 0.09 (9). Returning: subcategory clicks 0.55 vs 0.23 other, buys flat (8 vs 5).

**Q2 · first organic view / purchase within 10 min of the home request** (`shop.events`). Returning: 2,166 views and 488 buys after 10,855 requests; new: 497 and 90 after 4,543. Brand-new shoppers with no earlier event: median 52 min to the first view (66 of 688 within 10 min).

| predictor (returning) | first view hit | first buy hit |
|---|---|---|
| category = top history category / = last viewed category | 32.4% / 20.7% | |
| subcategory = top / last viewed in history / last viewed today | 10.3% / 3.9% / 3.7% | |
| product in viewed-today / carted-today / history carts / last 10 history views | 5.4 / 2.8 / 2.8 / 0.7% | 12.9 / 9.4 / 5.1 / 1.2% |
| top-10 best sellers of top category / segment / all-time / previous hour | 4.5 / 2.6 / 2.5 / 1.9% | 12.3 / 8.2 / 7.8 / 7.2% |
| new shoppers: all-time / segment / previous hour top-10 | 2.4 / 2.6 / 2.4% | 6.7 / 6.7 / 4.4% |

**Q3 · new shoppers' organic activity today** (14,627 purchases, 277k views). Caught by top-10 / top-50 lists: all-time 5.5 / 16.6%, segment 6.6 / 17.6%, previous hour 5.5 / 15.9%, today so far 3.6 / 11.1% (views 1.1 / 4.2%). First view, top-10 product share: 2.2–2.8% per segment, android-south 7.5% (top-50: 8–9%, 19%). Category shares move < 4 points between 4-hour blocks; history home is flat by hour (0.12–0.17%). Live trend lists do not beat the all-time list.

**Q4 · recency vs volume.** Organic: top category by volume 32% vs last-viewed 21%; top subcategory 10.3% vs last 3.9%. Carousel: carts in the top category and the last history session 0.53 (9 buys) vs not in it 0.33 (4); never-touched top-category products 0 (click 0.70) vs 0.15 (2, click 0.98); viewed in the last session, not carted: 3 clicks, 0 buys. Volume wins; recency at most ×1.5 on carts.

**Q5 · ceiling.** Best sellers on home: returning 0.15% (9 / 6,146), new 0.63% (16 / 2,555). Labels since 15:40: slate-h returning 1.49% (7 / 470), new 0 / 178; opal-h returning 0.40% (2 / 494), new 1.06% (2 / 188). rules (13:27–15:06): 0.23% (2 / 857), 0.82% (3 / 366). Explore on home: 0 buys, 1 click in 177 requests. Carts first, filled at the live rates above: **1.43% expected** for returning home requests.

## verdict
- Home is not low for everyone: carts convert at 0.2–0.9% per slot-weighted impression, as well as a product page. Carts are the home signal for returning shoppers; **both** (history ×38, live ×14–54 over never-seen). Bought-before stays at zero live.
- Favourite category: by rank (1 / 0.3 / 0.1), not share. Subcategory rank, brand, recency: no live effect.
- New shoppers: all-time best sellers × segment is as good as any list we can build from what we hold; today's views (subcategory ×3) is the one lift found, 9 buys.
- Reachable: returning ~1.0–1.4%, new ~0.7–1.0% → home ~1.0–1.2% against 0.4–0.6% now.

## next
`cold2` (carts ×5, ×10 twice; rank-based category; viewed ×1.5; today ×4 / ×3). Needs the state in `docs/hypotheses/cold2-state.md`; without it cold2 is cold1 minus the viewed-product noise. Measure click× of carts live per slot.
