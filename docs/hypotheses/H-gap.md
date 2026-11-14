# H-gap · what the leaders sell that we do not
- **status**: confirmed for today's carts and product conversion; home near its ceiling; `rules5` queued.
- **owner**: agent
- **claim**: our 1.34% against 2.27% for the leader is not on the home page. It is on view pages: products the shopper carted today in an organic session (40–44% of requests have one) convert 2.5–5 times the first recent view and we almost never show them first; and the product's own buys per view drives purchase about one power more than our appeal term gives it.
- **test**: every impression of `team_01.feedback` 14 Nov 09:00–17:20 UTC (78,354 requests, 791 purchases, all arms and fallback) classified by where the shown product stood in the shopper's world at request time, first match wins: bought (history, organic today or through our lists earlier), recent view (only / first / last / other), carted today (organic, before the request, not bought), viewed today, history cart, history view, same subcategory / category as a recent view, top history category, none. Rates are buys per slot-weighted impression (wconv, %, weight 1/log2(slot+1)). Routes: returning with views (56% of requests), new with views (24%), home returning (14%), home new (6%). Code: `eda/gap/pull.py`, `pull_carts.py`, `build.py`, `report.py`; SQL `sql/hypotheses/H-gap.sql`.

## result

### Home page (Q5, Q1 home rows)

| | home returning (10,926 req, 30 buys, 0.27%) | home new (4,583 req, 25 buys, 0.55%) |
|---|---|---|
| history cart, not bought | **22 buys**, wconv 0.36 | – |
| carted today | 1 buy, 0.25 (766 impressions, 0 at slot 1 in 136) | 2 buys, 1.35 |
| viewed today | 0, 0 (1,179 Σw) | 1, 0.59 |
| history view | 3, 0.02 | – |
| top category | 2, 0.06 | – |
| none | 2, 0.01 | 22, 0.11 |

- Returning, history carts by count: 1 cart 0.22 (11 buys), 2+ carts 1.0 (11 buys, ×4.5). Cart recency (days since, recency rank) is flat (0.59–0.79 across 0–61 days, all pages, 171 buys). Among carts, purchase grows as history buys^0.36 (all pages) to ^0.54 (home), not ^1 as cold2's best-seller base.
- Slot 1 on home returning: a history cart converts 0.50% per request (9 / 1,790), a top-category product 0.19% (1 / 519), anything else ≈ 0.
- New shoppers on home buy the all-time best sellers: rank 1 (p_adc3e6) wconv 0.30 (8 buys), ranks 2–3 0.18 (6), ranks 4–20 0.03–0.11. Their organic next purchase (111 within 10 min) is 96% outside every personal class; the shown list catches 5.4%, today's carts 1.8%.
- Ceiling: carts ordered by count, at the measured rates, give 1.36% for home returning if attention after slot 3 followed 1/log2; carts at slots 4–10 convert at half that (slot curve below), so 0.8–1.0% is realistic. New: 0.5–0.6%. **Home overall at most ~0.75–0.85% against ~0.6% now: +0.03–0.05 points on the team number.** The gap to the leaders is not here.

### Q1 · what is bought, view pages

| class | returning: buys (share) | wconv | Σw | new: buys (share) | wconv | Σw |
|---|---|---|---|---|---|---|
| bought before | 3 (1%) | 0.03 | 9,209 | 1 | 0.55 | 183 |
| recent view, only one | 25 (6%) | 1.17 | 2,143 | 31 (9%) | 2.33 | 1,333 |
| recent view, first of 2+ | 25 (6%) | 0.69 | 3,647 | 30 (9%) | 1.24 | 2,413 |
| recent view, last of 2+ | 3 (1%) | **0.10** | 2,961 | 6 (2%) | 0.33 | 1,837 |
| recent view, other | 8 (2%) | 0.30 | 2,669 | 9 (3%) | 0.53 | 1,706 |
| **carted today** | 21 (5%) | **1.72** | 1,223 | 26 (8%) | **6.37** | 408 |
| viewed today | 6 (2%) | 0.16 | 3,785 | 2 | 0.31 | 637 |
| history cart | 149 (38%) | 0.81 | 18,296 | – | | |
| history view | 31 (8%) | 0.07 | 46,515 | – | | |
| same subcategory | 22 (6%) | 0.29 | 7,483 | 49 (14%) | 0.54 | 9,045 |
| same category | 60 (15%) | 0.29 | 20,994 | 121 (35%) | 0.50 | 24,176 |
| top history category | 20 (5%) | 0.27 | 7,309 | – | | |
| none | 20 (5%) | 0.03 | 73,573 | 68 (20%) | 0.15 | 43,992 |

Carted today by slot: returning 2.10 / 2.42 / 1.07 at slot 1 / 2–3 / 4–10; new 6.96 / 8.96 / 4.41. Not a slot artefact.

### Q2 · ranked misses (all arms pooled; lost buys = moving the product to slot 1, net of what slot 1 sells now)

| class, route | has it (available) | shown / slot 1 / top 3 | wconv | lost per 1,000 route requests | per 1,000 of all requests |
|---|---|---|---|---|---|
| carted today, new with views | 39.5% | 10% / 2% / 4% | 6.37 (26) | 21.4 | **5.1** |
| carted today, returning with views | 44.4% | 12% / 2% / 5% | 1.72 (21) | 5.8 | **3.3** |
| history cart, returning with views | 95.0% | 45% / 11% / 25% | 0.81 (149) | 3.4 | 1.9 |
| only recent view, returning | 29.5% | 22% / 12% / 16% | 1.17 (25) | 2.1 | 1.2 |
| first recent view, returning | 62.9% | 20% / 8% / 13% | 0.69 (25) | 2.0 | 1.1 |
| only recent view, new | 31.2% | 28% / 18% / 23% | 2.33 (31) | 4.0 | 1.0 |
| first recent view, new | 68.3% | 27% / 11% / 20% | 1.24 (30) | 3.1 | 0.75 |
| history cart, home returning | 95.5% | 50% / 17% / 32% | 0.36 (22) | 1.7 | 0.23 |

Per arm, carted today in the top 3 when available: onyx 16%, onyx-n 21%, shale 12%, agate-h 31%, others 1–6%. rules4 (onyx) already shows history carts in the top 3 90% and first views 29–46%, so for rules4 the today-cart miss is most of what is left. The 5-to-1 ratio rests on 47 buys; take half of it as the planning number.

### Q3 · organic purchases in the 10 minutes after a request we did not sell

| route | organic buys / unsold requests | already bought (repeat, meaningless live) | caught by top-10 list: today's carts / today's views / history carts / recent views / our shown list |
|---|---|---|---|
| returning with views | 2,506 / 43,583 | 36.5% | 6.6 / 3.1 / 4.6 / 0.8 / 4.9% |
| new with views | 451 / 18,526 | 2.7% | 3.8 / 3.3 / 0 / 1.1 / 6.0% |
| home returning | 608 / 10,896 | 38.0% | 8.1 / 3.3 / 5.6 / 0 / 6.4% |
| home new | 111 / 4,558 | 2.7% | 1.8 / 0.9 / 0 / 0 / 5.4% |

The organic stream is a poor target: a third are repeats, and recent views (the carousel session) almost never reappear in it (the carousel's recent views are not in `shop.events`: 0 of 3,000 last views match an organic event; only 3.7% of last-viewed products were viewed organically that day). Today's carts are the best single predictor of it too.

### Q4 · timing and state (effects with ≥ 30 buys)

| factor | finding |
|---|---|
| product buys per view (history), within class × route, Poisson | buys ∝ bpv^1.4 × views^0.30 (750 buys); recent views bpv^2.0, carts ^1.0, subcategory/category ^2.0, others ^1.1. Clicks ∝ bpv^0.5–1.7. Top bpv quintile of recent views 2.33 against 0–0.44 for the rest. appeal carries bpv^0.5: **under-weighted by about one power** |
| history cart count (171 buys) | 1 / 2 / 3+ carts: 0.64 / 0.82 / 1.50 |
| history views of a carted product (171 buys) | 1 / 2–3 / 4+ views: 0.93 / 0.57 / 0.41 |
| cart recency, days since or rank (171 buys) | flat |
| time since today's cart (50 buys) | flat: 3.1 / 2.1 / 0.8 / 2.1 / 2.7 for < 10 min / 10–30 / 30–60 / 1–2 h / > 2 h. **Carts older than 2 h are 31 of 50 buys** |
| events today, recent views (137 buys) | 0 events 1.66 (mostly new shoppers), 1+ 0.5–0.77, flat |
| seconds since the last view (137 buys) | flat (0.65–0.92) |
| price against the shopper's usual (carts, 192 buys) | flat except 1.25–2× (0.44 against 0.72–0.81) |
| price cut (catalog_updates, Sports & Outdoors at 16:30, Home & Garden 13:30–15:30) | cut products 11 buys against 19 expected at their class × route × category rate; clicks equal (50 against 50 expected in Sports). Too few buys to call; **no support for the +boost rules4 gives** |
| slot | 37% of buys at slot 1, 67% in slots 1–3. Carts (least ordered by us) per weight: 1.0 / 1.09 / 1.01 at slots 1–3, then 0.34–0.96 (mean ~0.6) at 4–10: attention falls faster after slot 3 than 1/log2. **The top 3 is the lever** |

### Q6 · fields we ignore, regularities

| table | columns | not used by our strategies |
|---|---|---|
| `shop.requests` | request_id, ts, user_id, is_new_user, context.page/device/region, recent_views[product_id, ts] | recent_views.ts (seconds since the last view: flat) |
| `shop.events` | ts, user_id, session_id, event_type, product_id, price_eur, device, region | session_id, price_eur (price at view: changes since view, 0 buys in 458 Σw, too few), device/region (taken from the request) |
| `team_01.feedback` | request_id, ts, shown, served_by, fallback_reason, latency_ms, clicked, purchased, revenue_eur, model_version | revenue_eur, latency_ms |

- request_id first hex digit: 0.79–1.19% per digit, no pattern; request ms: 1.00 / 1.01 / 1.01%; hour: 0.61% (11 h) rising to 1.52% (17 h), our arms improving.
- Carousel sessions and organic sessions are separate processes: the carousel's recent views do not appear in `shop.events`, so "same session" carts do not exist; today's carts come from earlier organic sessions.
- `model_version` is empty on 60,901 of 78,354 feedback rows (rows from before labels and the fallback).

### Why the old carousel converted 1.40% (history) against ~0.6% for best sellers live

| | history carousel |
|---|---|
| page mix | home 20% at 0.14%, product and category 80% at 1.71–1.72%: the same mix as live |
| non-home, by shown product (1/8 of shoppers, 3,501 buys) | **bought before: 1,689 buys (48%)**, wconv 3.8; recent view 229 (7%), 2.0; same category as the last view 1,583 (45%), 0.185; other category: no impressions |

- Half of the history carousel's sales are repeat purchases, which live does not allow. Without them non-home is ~0.9% and the whole carousel ~0.75%, about the live best-seller level (0.55–0.7%).
- The rest is the old policy itself: it showed best sellers **of the session's category** (every shown product was in the last view's category). Our live same-category rates (0.29 returning, 0.50 new) already beat its 0.185, and rules4 does this. Nothing left to reproduce.
- Product age (catalog created_at, 60–900 days): no effect at equal popularity and conversion (Poisson coefficient on log age −0.05 for buys, +0.02 for clicks; quintiles 134/145, 222/169, 104/108, 154/175, 146/164 observed/expected).

## verdict
- **Biggest miss: today's organic carts.** 40–44% of view requests have one, it converts 1.7% (returning) and 6.4% (new) per weighted impression against 0.7% / 1.2% for the first recent view, and we put it at slot 1 in 2% of cases. ~8 lost buys per 1,000 requests pooled, ~4 at half strength.
- **Product conversion is under-weighted**: purchase ∝ bpv^1.4–2 within each class; our appeal uses bpv^0.5.
- Recent views: the only view ×1.7–1.9 the first of several; the last of several converts below a same-subcategory product (9 buys, consistent with H-reshow-rank).
- History carts: by count (×2.3 for 3+), not recency; a carted product viewed many times converts less.
- Home is near its ceiling; cold2's design is right, with a too-steep popularity base among carts.
- Contradicts current beliefs: the price-cut boost (no support live); "history cart = recent view": history carts convert as well as first views (0.81 against 0.69, returning); popularity among carts matters as buys^0.4, not ^1.

## next
- `rules5` (queued): today's carts ×30 above the first view (×12), only view ×18, last of several ×3, × (bpv/0.2), history carts × count and × views, no price-cut boost; home = cold2 with carts on (buys+5)^0.5. Dry run on the newest 300 live requests: 300/300 valid, 0.9 ms median, 2.1 ms p95; top 3 differs from rules4 on 262/300 (home 54/60 because home now uses cold2's logic); slot 1 is a today cart on 47 of 240 view requests.
- **State addition needed** (not made): `State._today_events` loads only the last 120 minutes at start, so after a restart today's carts older than 2 h (31 of 50 cart-today buys) are missing. Change the initial load for `add_to_cart` rows to the start of the UTC day (`ts::DateTime64(3) >= toStartOfDay((SELECT max(ts::DateTime64(3)) FROM shop.events))`), keep 120 minutes for views, and add `def today_carts(self, user_id) -> dict[str, int]: return self._today_carts.get(user_id, {})`. rules5 reads `_today_carts` through `getattr` until then.
- Read rules5 against shale and rules4 on new shoppers with views first: that is where the today-cart effect is largest.
