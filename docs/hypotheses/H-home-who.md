# H-home-who · who the home-page shoppers are and what predicts their purchase
- **status**: answered (diagnosis, no strategy). Run 14 Nov 22:40–23:55 UTC on all live data 09:00–22:33 UTC.
- **owner**: agent
- **claim**: home requests (no recent views, 20% of traffic) convert at the baseline's rate because the shoppers are different, or because the lists are wrong.
- **test**: `eda/home/pull.py` (one row per live request with the shopper's `shop.events` before and in the 30 min after, plus history counts; organic purchases, carts, views, last history session and purchase, catalogue updates into `data/home/`), `eda/home/who.py` (slices, Q4–Q6), `eda/home/impressions.py` (precision per product class on our home lists), `eda/home/generators.py` (Q2–Q3 coverage and hit@10), `sql/hypotheses/H-home-who.sql` (the aggregates in RawTree). Cold2 / ranker2 organic numbers from `q2q replay baseline cold2 ranker2 --hours 6 --organic 9000` (16:41–22:41 UTC). "Ours" = `served_by = team`: 21,171 home requests, 90 purchases, 534 clicks (0.43 ± 0.04%, click 2.52%); cold2 + ranker2 only 0.46 ± 0.06% (54).

## result

### 0 · Two facts that frame everything
- **Home = no recent views exactly** (29,400 requests, all `page = home`; no product or category page lacks views).
- **Requests and `shop.events` are separate streams.** Only 6.1% of the last recent view of a request appears anywhere in the shopper's `shop.events` today; the gap from the shopper's last event to a request has the same distribution for home and other requests (median 40 min), and the next event after it too (median 38 min). An organic purchase in the 30 min after the request happens for **10.33 ± 0.18% of home requests and 10.33 ± 0.09% of requests with views**; views in the next 30 min 39.5% vs 39.2%. The organic stream does not know about our requests or their pages: it measures the shopper, not the session.

### Q1 · Who (our home lists, conversion and click in %, ± se, (purchases))

| slice | share | conv | click |
|---|---|---|---|
| shopper with history | 70% | 0.38 ± 0.05 (56) | 2.72 |
| no history, events earlier today (= new shopper) | 29% | 0.55 ± 0.09 (34) | 2.06 |
| truly unknown (no history, no event before) | 0.5% (113) | 0 | 1.8 |
| android × Andalucía/Canarias/Murcia | 10% | **0.97 ± 0.22** (20) | 4.13 |
| other segments | 90% | 0.37 ± 0.04 (70) | 2.35 |
| device android / ios / web | 34/33/33% | 0.45 / 0.40 / 0.43 | flat |
| organic purchases earlier today 0 / 1 / 2–3 / 4+ | 38/22/21/20% | **0.20 / 0.33 / 0.44 / 0.96** | 1.5 / 2.0 / 3.2 / 4.5 |
| carts earlier today 0 / 1–2 / 3–5 / 6+ | 25/30/21/24% | **0.21 / 0.14 / 0.49 / 0.95** | 1.1 / 1.8 / 2.8 / 4.7 |
| history purchases 0 / 1–5 / 6–15 / 16–40 / 41+ | 33/18/21/17/11% | 0.51 / 0.24 / 0.25 / 0.47 / 0.75 | 1.9 / 1.6 / 2.4 / 3.7 / 4.1 |
| organic purchase < 30 min before the request | 10% | 0.72 ± 0.18 (16) | 3.6 |
| gap since last event < 10 min / 10–30 / 30 min–2 h / > 2 h | | 0.27 / 0.39 / 0.46 / 0.48 | flat |
| first request of the day / after a home request / after a request with views | 32/14/54% | 0.46 / 0.34 / 0.43 | flat |
| **previous request bought from our list** | 0.6% (137) | **6.6 ± 2.1** (9) | 13.1 |
| previous request clicked, no buy | 1.7% (370) | 1.35 | 5.7 |
| hour 12–22 UTC | | 0.24–0.85, no pattern beyond arm changes | |

- Same "previous request bought" effect on requests with views: 11.8% (600) vs 1.73%. Median gap 1.7 h, the bought product is in another category in 6 of 9 cases: **a shopper-level buy propensity, not session momentum.**
- Conversion is concentrated in active shoppers: the 44% of home requests from shoppers with 3+ carts today give 78% of the purchases (70 of 90). Shoppers with no cart today (25% of requests, ~40% with none left unbought) convert 0.19–0.21%.
- Truly unknown shoppers are negligible (0.5%). "New shopper" on home means "has events today": 91% have views, 75% of all home requests have carts today.

### Q1b · Precision per product class on our home lists (buy % per slot-weighted impression, w = 1/log2(slot+1))

| class of the shown product | Σw | clicks | buys | click %/w | buy %/w |
|---|---|---|---|---|---|
| carted today (> 1 h ago), not bought | 4,528 | 62 | 18 | 1.37 | **0.40 ± 0.09** |
| — of which shopper has no history (new) | 2,791 | 42 | 13 | 1.51 | 0.47 ± 0.13 |
| carted today < 1 h | 842 | 8 | 2 | 0.95 | 0.24 ± 0.17 |
| history cart, not bought | 22,593 | 261 | 41 | 1.16 | 0.18 ± 0.03 |
| never touched in history | 52,427 | 207 | 45 | 0.39 | 0.086 ± 0.013 |
| viewed today, not carted | 5,317 | 26 | 2 | 0.49 | 0.04 ± 0.03 |
| history viewed only | 20,305 | 66 | 4 | 0.33 | 0.020 ± 0.010 |
| history bought | 866 | 0 | 0 | 0 | 0 |
| all | 96,192 | 534 | 90 | 0.56 | 0.094 |

**Within the same lists** (5,878 home lists that show a today cart): today cart 0.37 ± 0.08 (20), history cart 0.15 ± 0.04 (14), other 0.067 ± 0.024 (8). So today's carts beat history carts ×2.5 and everything else ×5.5 for the same shopper; this is not only the shopper's propensity. Lists from shoppers with no today cart: other products 0.027%/w, history carts 0.14%/w.

60.5% of our home requests have at least one carted-today product not bought (median 2, p75 3, p90 5); our lists show 0.45 of them on average, 22% of those available.

### Q2–Q3 · What they buy, and each generator alone (`eda/home/generators.py`)
Organic = every organic purchase of the shopper in the 30 min after a home request (2,660 requests with one; complete windows). List = the shown product bought from a home list (106, team and fallback). Coverage = a target inside the generator's full candidate set; size = mean size of that set; hit@10 = a target in the generator's own top 10. Precision ≈ coverage / size. ± se.

| generator (ranking) | organic coverage | size | **organic hit@10** | history shoppers hit@10 | new shoppers hit@10 | list hit@10 (all / history / new) |
|---|---|---|---|---|---|---|
| history repurchase (buys, views) | 30.8 ± 0.9 | 46 | 19.8 ± 0.8 | 24.2 | n/a | **0 / 0 / –** (trap) |
| history carts not bought (carts, views) | 11.0 ± 0.6 | 30 | 5.6 ± 0.4 | 6.8 | n/a | 31 / 53 / – |
| history viewed only (views) | 22.3 | 536 | 1.7 ± 0.3 | 2.1 | n/a | 0 / 0 / – |
| last history session | 2.0 ± 0.3 | 4 | 2.0 ± 0.3 | 2.4 | n/a | 2 / 3 / – |
| co-purchase of last history purchase | 29.1 | 50 | 13.5 ± 0.7 | 16.5 | n/a | 28 / 48 / – |
| favourite subcategory, best sellers | 19.9 | 112 | 11.8 ± 0.6 | 14.4 | n/a | 12 / 21 / – |
| favourite category, best sellers | 47.9 | 546 | 13.0 ± 0.7 | 15.8 | n/a | 25 / 42 / – |
| all-time best sellers | 20.9 | 50 | 7.4 ± 0.5 | 7.5 | 6.7 ± 1.2 | 50 / 39 / 64 |
| today's best sellers so far | 21.4 | 50 | 7.3 ± 0.5 | 7.5 | 6.5 ± 1.1 | 46 / 37 / 57 |
| last hour's best sellers | 7.4 | 10 | 7.4 ± 0.5 | 7.4 | 7.2 ± 1.2 | 49 / 42 / 57 |
| today's best sellers in device × region | 21.5 | 50 | **8.6 ± 0.5** | 8.7 | **8.2 ± 1.3** | 50 / 39 / 64 |
| viewed today (latest first) | 21.8 | 77 | 4.2 ± 0.4 | 4.3 | 4.1 ± 0.9 | 7 / 7 / 7 |
| carted today (latest first) | 14.9 ± 0.7 | **12** | 10.2 ± 0.6 | 11.4 | 5.2 ± 1.0 | 16 / 8 / 29 |
| best sellers of today's last-viewed subcategory | 7.4 | 84 | 4.7 ± 0.4 | 4.8 | 4.3 ± 0.9 | 9 / 8 / 12 |
| on a price cut, best sellers | 6.7 | 570 | 1.7 ± 0.2 | 1.7 | 1.7 ± 0.6 | 1 / 0 / 2 |

Relations of the organic purchase: bought in history 30.8% (history shoppers 37.5%), same top category 47.9% (58.4%), same top subcategory 19.9% (24.3%), same top brand 14.7%, bought earlier today 9.1%. Of list purchases: bought in history **0%**, same top category 43% (74% of history shoppers), bought earlier today 0%.

Same replay window, `organic10` on no_views (excludes shown products, `q2q replay`, 1,119 requests): **baseline 5.7 ± 0.7, ranker2 3.9 ± 0.6, cold2 2.1 ± 0.4**; list hit@10: cold2 84 (56), ranker2 89 (56), in-sample.

- Organic purchases are the wrong target for home. Their top generator is repurchase (31% coverage, hit@10 20%), which is worth exactly zero live (0 of 106 list purchases, 0 clicks in 866 w of bought products). The organic log was generated without no-rebuy and without our requests (section 0). Best sellers beat both of our arms on organic10. Use organic only to rank *non-repurchase* generators against each other.
- Precision per candidate on organic: carted today 1.2% per candidate (14.9 / 12), co-purchase 0.58%, last session 0.5%, any top-50 best-seller list 0.42%, history carts 0.37%, viewed today 0.28%, favourite subcategory 0.18%, price cut 0.01%.
- Co-purchase of the last purchase is mostly popularity: 61% of its top 10 are all-time top-50 products. Its hit@10 (13.5) equals favourite-category best sellers (13.0); it adds nothing distinct.
- Global popularity lists tie: all-time, today, last hour 7.3–7.4; device × region today 8.6 (+1.2, about 2 se). **The last hour does not beat all-time.** Personal category ×2 over any global list (13.0–15.8 vs 7.4) for history shoppers.
- List hit@10 only sees what we showed (our lists are best sellers and carts), so it is biased to those generators; read it for the zero of repurchase and for new shoppers (all-time / segment best sellers 64%, today's carts 29% with 9 candidates).

### Q4 · Is the low rate structural?
- Organic purchase in 30 min after the request: home 10.39 ± 0.19%, with views 10.29 ± 0.09% (in 10 min: 3.79 vs 3.92%). History shoppers 12.1% after home vs 12.0% after views; new 6.4 vs 6.3%. **The shoppers who land on home buy organically exactly as often as the others.** The organic stream cannot show the session, so this does not prove home sessions could convert like product pages, but it rules out "home shoppers are non-buyers".
- The home/other gap is the same for every shopper class (history 0.32 vs 1.22, new 0.55 vs 2.21: ×4 each). The simulator's request-level intent (recent views) is what is missing, not the shopper.

### Q5 · Does a home click pay off later?
After a home list (complete 30-min windows): next request within 30 min 3.6% (bought), 12.0% (clicked, no buy), 12.4% (no click). Next request converts 0 of 50 after a click without purchase, 23 of 2,430 (0.94%) after no click. Organic views in the next 30 min: 2.55 after a click vs 2.77 without. **No sign a home click feeds later requests**, and only 12% of home lists are followed by another request within 30 min, so even a real carry-over would be worth little. Optimise home for purchase, not click.

### Q6 · What converting lists look like (our home lists)

| lists | n | distinct categories | distinct subcats | mean price € | share in history | share history carts |
|---|---|---|---|---|---|---|
| bought | 90 | 2.82 ± 0.18 | 6.19 ± 0.22 | 44.6 ± 3.9 | 0.46 | 0.33 ± 0.04 |
| not bought | 20,942 | 3.42 | 6.84 | 36.0 | 0.45 | 0.22 |

- Category diversity: 1 category 0.79% (24), 2: 0.57%, 3+: 0.27–0.30%. Holding cart share above 0.3: 1–2 categories 0.93% (23) vs 3–4: 0.28% (5). This is the known category-rank effect (top category ×10) rather than a reward for focus; no sign diversity is rewarded.
- Price: lists with mean > 70 € convert 0.72% vs 0.18% under 15 €, but **inside a converting list the bought product is cheaper than the list mean** (median ratio 0.45; above the list median in 30% of 70 cases). The list-level price effect is a confound (carts and expensive categories); within the list cheap wins, as in `price-sensitivity`.
- Share of products from history: equal (0.46 vs 0.45); what matters is carts (0.33 vs 0.22; lists with ≥ 30% carts 0.70% vs 0.37% with none).
- Position: the bought slot after a list purchase was 1 in 4 of 9; no new evidence beyond 1/log2(k+1).

## verdict
- **Not structural on the shopper side.** Home shoppers buy organically exactly as often as the others (10.3% vs 10.3% in 30 min), in every class. The home gap is ×4 in every shopper class: the missing piece is the session intent, not a different population.
- **Conversion on home is a cart business.** Today's carts not bought: 0.40%/w (×2.5 over history carts within the same lists, ×5.5 over other products). History carts 0.18%/w. Everything else 0.03–0.09%/w. Viewed-not-carted (today or history) is at or below never-touched (0.02–0.04 vs 0.086). Bought before: 0.
- **Today's carts are under-used**: available on 60% of our home requests (median 2), shown 0.45 per list, 22% of those available. Upper estimate with today's carts in the top slots (up to 3) and the rest at today's rates: 0.43% → **0.66%**; all of them first: 0.74%. Expect less, because the measured carts were picked by cold2/ranker2: **+0.15 to +0.25 points**.
- **Who converts**: active shoppers. 3+ carts today: 45% of requests, 78% of purchases. A shopper who bought from our list before converts 6.6% on home (11.8% with views): a strong per-shopper buy propensity. It scales the whole list, so it does not change which list to show; use it to stratify evaluations, not as a ranking signal.
- **Segment**: android × south 0.97% vs 0.37% (×2.6), confirmed again. Device alone, region alone except Andalucía, hour, gap since last event, first request vs later: flat or noise.
- **For the trending strategy (hot1)**: global lists tie (all-time = today = last hour, 7.3–7.4 organic hit@10); device × region today +1.2 (about 2 se); favourite category ×2 over any global list. The products these lists fill on home convert 0.03–0.07%/w; doubling that on the ~70% of slot weight they hold is worth at most +0.1–0.2 points. On shoppers with no cart left (40% of requests, 0.19% now) that is the whole game, and the ceiling is low.
- **Click is not a proxy**: no carry-over from a home click to later requests (0 of 50; only 12% of home lists are followed by a request within 30 min).
- **Noise / not supported**: diversity (lower diversity converts better, but that is top-category rank, not focus), list price (confounded; inside a list the cheaper product wins), position beyond 1/log2, hour of day, gap since last event, "after an organic purchase" (0.72 ± 0.18, overlaps the active-shopper effect), "first request of the day". Price cuts: 1.7% hit@10, nothing.

## next
- cold2 / ranker2: separate today's carts from history carts (today ×2.5 over history), today's carts always candidates and at the top; drop `TODAY_PRODUCT` ×4 on viewed-not-carted (2 buys in 5,317 w). Measure live per-slot rate of today's carts at slot 1–3.
- hot1: rank trending products inside the shopper's top category (history) or segment (new shoppers), never globally; it is the filler after carts, not the head of the list.
- Evaluate home arms on list purchases with a stratum for active shoppers (carts today 3+); do not use `organic10` (it rewards repurchase and popularity).
