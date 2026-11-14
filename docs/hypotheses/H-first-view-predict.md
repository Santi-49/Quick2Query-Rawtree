# H-first-view-predict · what a new shopper with no recent views views first
- **status**: refuted as a lever: first views are diffuse and late.
- **owner**: agent
- **claim**: a brand-new shopper's first view after a home request is concentrated enough by segment to target.
- **test**: `sql/hypotheses/H-first-view-predict.sql`, run 14 Nov ~16:20 UTC. Live `shop.requests` (new shoppers whose first request is home) joined to `shop.events`; history first sessions.

## result
- **Timing**: new shoppers with no event before the home request (688): median 52 min to the first view, 66 within 10 min. With earlier events today (2,007): median 35 min, 538 within 10 min.
- **Concentration** of the first viewed product, share of the segment's top 10 / top 50 (top category 13–21%, Books & Media first; top 3 categories 37–44%):

| segment | history first session | live after home | live first view today (users) |
|---|---|---|---|
| android-south | 7.8 / 18.0% | 10.3 / 28.7% (223) | 7.5 / 18.7% (1,332) |
| android elsewhere | 2.7 / 8.2% | 5.1 / 17.7% (594) | 2.8 / 9.4% (3,211) |
| ios | 2.4 / 7.9% | 3.5 / 14.6% (720) | 2.2 / 8.3% (4,638) |
| web | 2.4 / 7.7% | 4.6 / 16.3% (760) | 2.4 / 8.5% (4,475) |

- New shoppers with earlier views today: next category = most viewed today 24%, in today's top 3 43%, seen today 51%; the same product 1.8%. 41% of their later purchases fall in today's top category.
- History, returning: first category of a session = the user's top category 33%, in their top 3 62%.

## verdict
The first view of a brand-new shopper cannot be targeted beyond the best sellers × segment: top-10 product share is 2–3% (7–10% for android-south). Today's earlier views are a better guide (see `H-home-ceiling.md`).

## next
State for today's views (`docs/hypotheses/cold2-state.md`).
