# 03 · Carousel history (`shop.history_sessions`)

2,000,000 requests, 20M impressions, 59,698 users. Queries: `eda/03-carousel.sql`, `03b`–`03f`, `07-checks.sql`. Rates are per request unless a slot is named.

## Base rates

| Page | Requests | Click % | Purchase % | Buy after click |
|---|---|---|---|---|
| product | 1,119,265 | 4.48 | 1.72 | 38% |
| category | 480,186 | 4.49 | 1.71 | 38% |
| home | 400,549 | 0.79 | 0.14 | 18% |
| all | 2,000,000 | 3.75 | 1.40 | |

- At most one click per request. The purchase is always the clicked product. Always 10 distinct products.
- Home means no recent views. It is 20% of requests.
- Stationary by day and by hour.

## What the old carousel did

- **Every request shows products from one category only.** On product and category pages it is the category of the last viewed product. On home it is one category, usually not the shopper's.
- Not personalised: a product's propensity at a slot is a constant.
- 4,691 products were ever shown. The top 200 take 69% of impressions, the top 1,000 take 96%.
- Propensity per slot: mean falls from 0.109 (slot 1) to 0.049 (slot 10), range ~0 to 0.6.
- **The log says nothing about showing a product from another category.**

## Slot

Same product (`p_adc3e6`) at each slot:

| Slot | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| Click % | 4.45 | 2.77 | 2.23 | 1.82 | 1.66 | 1.52 | 1.47 | 1.40 | 1.22 | 1.18 |
| Relative | 1 | 0.62 | 0.50 | 0.41 | 0.37 | 0.34 | 0.33 | 0.31 | 0.27 | 0.27 |
| 1/log2(slot+1) | 1 | 0.63 | 0.50 | 0.43 | 0.39 | 0.36 | 0.33 | 0.32 | 0.30 | 0.29 |

- Attention follows the DCG discount. Slots 1–3 hold 47% of the total weight.
- Buy after click also falls with slot, from 42% to 31%.
- No sign that slots compete: with a strong product at slot 1, slots 2–10 get more clicks, not fewer (3.99% against 2.80%).

## What makes a shown product convert (slot 1, product and category pages)

| Relation to the shopper | Click % | Purchase % |
|---|---|---|
| Same product as the last view | 9.30 | 6.70 |
| Same subcategory as the last view | 1.81 | 0.84 |
| Same brand | 1.19 | 0.47 |
| Same category only | 1.08 | 0.42 |

| Shown product (slots 1–3) | Purchase % |
|---|---|
| In recent views, any position | 3.6–4.6 |
| Not in recent views | 0.29 |
| Viewed on earlier days: never / 1–2 / 3–9 / 10+ times | 0.09 / 0.43 / 1.55 / 6.96 |
| Shopper viewed its subcategory before: never / 1–4 / 5–19 / 20+ times | 0.07 / 0.22 / 0.44 / 1.27 |
| Bought before: never / yes | 0.12 / 2.30 |

- Home page: 0.77% when the shown category is the shopper's most viewed one, 0.07% otherwise.
- Conversion falls with the number of recent views: 2.06% with one view, 1.39% with six.

## Product, price and context

| Category (non-home) | Purchase % |
|---|---|
| Books & Media | 4.12 |
| Toys & Baby | 2.83 |
| Fashion | 2.10 |
| Beauty & Health, Electronics | 1.44, 1.43 |
| Sports, Computers & Gaming, Home & Kitchen | 1.14, 1.00, 0.71 |
| Home & Garden, Pets | 0.18, 0.15 |

- Product appeal at slot 1 (136 products with 2,000+ impressions): click rate 0.18% at the 5th percentile, 0.78% median, 2.26% at the 95th.
- Price at slot 1: under 10 € converts at 0.68%, 35–60 € at 0.14%, above 120 € at 0.38%. Much cheaper than the last view: 0.57% against 0.31–0.39%.
- **Android in Andalucía, Canarias and Murcia** (10% of traffic) converts several times better in four categories: Fashion 8.9% against 1.2%, Home & Kitchen 4.4% against 0.3%, Electronics 4.6% against 1.1%, Computers & Gaming 3.4% against 0.7%. Milder in Toys (5.1% against 2.6%) and Books (4.9% against 4.1%). No effect in Pets, Sports, Home & Garden, Beauty. Device and region are fixed per user.

## Takeaways

- Ranking order of evidence: the product just viewed, any recently viewed product, products the shopper viewed often before, the same subcategory, the shopper's favourite category, product appeal.
- The log cannot evaluate a cross-category list, a personalised home page or an unpopular product. Those need live data.
- The repeat-purchase signal here is positive. Live it is negative (see `06-feedback.md`). **History and the live model differ in at least this point.**
