# 05 · Live stream (`shop.requests`, `shop.events`, `shop.catalog_updates`)

Live since Saturday 09:00 UTC. Measured after 3.5 hours. Queries: `eda/05-live.sql`, `07-checks.sql`.

## Requests

| | |
|---|---|
| Rate | exactly 3 per second, 10,800 per hour |
| Users per hour | ~31,900 active, 1.41 requests per user |
| New shoppers (`is_new_user`) | 30% |
| Home page, no recent views | 19.5% |
| New shopper and no recent views | 5.5–6% |
| Recent views on other pages | 2.54 on average |
| Cold requests, organisers' definition | ~34% of non-home requests |
| Requests with a new product in recent views | 5.25% of non-home requests |

- Returning shoppers are in the history: 16,967 of 16,973.
- New shoppers are not in the history at all. Their device, region and page mix equals that of returning shoppers.
- Page mix equals history: product 56%, category 24%, home 20%.

## Store changes so far

| Change | When (UTC) | What |
|---|---|---|
| Stock-outs | all the time | 3 products every 5 minutes, back after about 1 hour, ~36 out at any time |
| New products | 10:00, once | 100 products, 55 subcategories, 60 brands. First organic view after ~159 s |
| Price change | 10:30, once | all 620 Pets products, −20% |
| Trend | from 11:30 | two subcategories, Kettles and Aquariums. Views of their top products jump about 5 times at the half hour |

- New products: buy per view 6.5% against 5.3% overall. They are popular at once.
- Pets after the price cut: share of views 9.9% → 11.4%, buy per view 3.2% → 3.5%. A modest effect.
- Outside the trend, product view shares match history (lift between 0.80 and 1.16 for 90% of products).
- Best sellers go out of stock too. The fallback has used 15 different lists in 3.5 hours.

## Stock timing

Three of our answers were judged invalid. Each was within 4 seconds after a stock row at a 5-minute mark:

- two contained a product that went out of stock 4 s earlier;
- one contained a product whose `back_in_stock` row was 3 s old.

So out-of-stock applies at once, and back-in-stock is honoured late. All three answers also took just over 3 s, because the starter recomputes its list at those moments.

## Takeaways

- **One request in three is cold.** A third of the shoppers have no history, and a fifth of the requests have no recent views.
- Shoppers come back rarely within the event (1.4 requests each). Per-shopper learning inside the event is weak. Learning per segment and per product is what transfers.
- Each kind of change appeared once, on a schedule: new products, then a price cut, then a trend. Expect all three inside the 2-hour final.
- A trend is a step change in a whole subcategory. Live view counts per subcategory over 10–15 minutes detect it.
- Stock rule for the router: drop a product as soon as its out-of-stock row appears, and wait about a minute after a back-in-stock row.
