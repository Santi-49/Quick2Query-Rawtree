# 06 · Our feedback (`team_01.feedback`)

24,826 requests up to 12:25 UTC. Every answer so far is the best-seller list, ours or the fallback's. Queries: `eda/06-feedback.sql`.

## Reliability

| Period (UTC) | What happened |
|---|---|
| 09:00–10:58 | nothing running, fallback |
| 10:58–11:09 | starter running |
| 11:09–12:03 | laptop went to sleep, fallback |
| 12:03 onwards | starter under a supervisor, 99.9% answered on time |

- That gap is the 16.5% on-time figure. Latency was never the cause: 0 late answers.
- Latency of our answers: p50 1.4–1.5 s, p95 2.3 s, p99 2.7 s, max 3.5 s.
- 3 answers invalid, all at a stock change (see `05-live-stream.md`).
- Feedback for a request exists about one second after the request.

## Outcomes on the best-seller list

| Served by | Requests | Click % | Purchase % |
|---|---|---|---|
| Fallback | 19,511 | 2.37 | 0.71 |
| Us | 5,312 | 2.52 | 0.90 |

| Page | Returning: purchase % | New shopper: purchase % |
|---|---|---|
| product | 0.65 | 1.50 |
| category | 0.58 | 1.13 |
| home | 0.18 | 0.56 |

- About 260 clicks and 75 purchases per hour over all traffic.
- New shoppers convert twice as well as returning ones on best sellers.

## Cross-category, seen for the first time

Same list for everyone, so the difference comes from the shopper. Slots 1–3:

| Shown product against the last viewed product | Impressions | Click % | Purchase % |
|---|---|---|---|
| Same product | 91 | 5.5 | 4.4 |
| Same subcategory | 1,154 | 1.82 | 0.52 |
| Same category | 5,890 | 1.48 | 0.63 |
| Other category | 52,952 | 0.39 | 0.13 |
| Home, no views | 14,400 | 0.29 | 0.06 |

- **A product from the shopper's current category converts about 5 times better than one from another category.** On product and category pages, 89% of what the best-seller list shows is from another category.

## Repeat purchases, live

Returning shoppers, all slots:

| Shopper and shown product, from history | Impressions | Click % | Purchase % |
|---|---|---|---|
| Bought before | 12,486 | 0.10 | 0.024 |
| Viewed before, never bought | 27,007 | 0.51 | 0.133 |
| Never seen | 134,067 | 0.14 | 0.041 |

- **Live, an already-bought product is worth less than a product the shopper never saw**, and five times less than one they viewed and did not buy. In the history log the same signal is strongly positive.
- This explains why returning shoppers do worse on best sellers: many already own them.
- Counts are small (3 purchases, 12 clicks in the first row). Confirm with a probe.

## Segment

| | Returning: purchase % | New: purchase % |
|---|---|---|
| Android in Andalucía, Canarias, Murcia | 1.44 | 3.99 |
| Everyone else | 0.44 | 0.95 |

The segment found in history is alive, and it holds for new shoppers. Device and region are known on every request.

## Takeaways

- Three rules already beat the best-seller list on paper: stay in the shopper's category, skip what they bought, prefer what they viewed and did not buy.
- A model trained on the history log alone would push already-bought products. Anything learned from history needs a live check.
- Device and region give a usable prior for a shopper with no history.
