# 04 · Organic history (`shop.history_events`)

12M events, 59,841 users, 60 days. Queries: `eda/04-organic.sql`, `03f-rebuy.sql`, `07-checks.sql`.

## Sessions and users

| | |
|---|---|
| Sessions | 2,500,000, about 50,000 per hour live |
| Views per session | mean 4.14, median 3, 90th percentile 8 |
| Sessions with a cart / a purchase | 32.2% / 18.6% |
| Sessions inside one category | 55.2% (1.58 categories on average) |
| Sessions per user | median 25 |
| Users who ever bought | 86.6%, 9.2 purchases on average |
| Share of a user's views in their top category | 37.9% (8 of 10 categories viewed) |

## Funnel

- Strict: a purchase always follows a view and an add-to-cart of the same product in the session.
- 10.7% of viewed products are carted. 50.5% of carted products are bought.
- Buy per view by category runs from 8.5% (Books & Media) to 2.3% (Home & Garden).
- Top 100 products hold 28.7% of purchases, top 1,000 hold 79%.

## Next view

| The next view in a session is in the same... | Share |
|---|---|
| Subcategory | 72.8% |
| Category | 79.5% |
| Brand | 12% |
| Product | 1.7% |

## Repeat purchases

- 50,985 of 465,336 user-product pairs were bought more than once (11%), up to 85 times.
- Gaps between repeats are mostly 7–30 days.
- After a first purchase 38.6% view the product again and 15.5% buy it again. For viewed-but-not-bought products: 10% and 1.1%.

## Stability

- No price changes, no new products, no trends in 60 days. The highest weekly peak of any product is 1.33 times its average (99th percentile).
- All 5,000 products are present from the first week.

## Relation to the carousel log

- Recent views in a carousel request are the shopper's latest organic views.
- Every carousel purchase also appears as an organic purchase event.

## Takeaways

- A session is about one subcategory. The last view is the best single predictor of the next.
- Shoppers have a favourite category but browse widely. Long-term taste is a prior, the session is the signal.
- History contains none of the changes the live stream has. Reactions to new products, prices and trends can only be learned live.
- Organic sessions give an unbiased next-item test for candidate generation: no old-carousel bias.
