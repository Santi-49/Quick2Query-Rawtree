# What we believe about the hidden simulator

The single place where our knowledge of the simulator accumulates. Update it after every hypothesis verdict. We do not rebuild the simulator; we record what it reacts to and how strongly.

Status of this version: first verdicts from the initial EDA, Saturday 14 Nov 12:30 UTC. Evidence is in `docs/findings/01`–`07`. "History" means the 60-day logs, "live" means our feedback since Saturday.

## Stated by the organisers

- All shoppers, sessions and outcomes come from a simulator with a secret seed. The catalogue is synthetic.
- All teams receive the same shoppers at the same time.
- Shoppers look at the first slots much more than the last.
- Whether a shopper buys is a coin flip on a probability. The score uses the probability of buying given the 10 products shown.
- A shopper who already bought a product tends not to want it again, so what we sell changes later scores.
- The old carousel was "best sellers plus a bit of randomness"; its log is biased to popular products and carries a propensity per slot, conditional on the slots above.
- The store changes: new products with only a description, trends visible in live events, announced price changes, stock-outs.
- The final round has new shoppers, new products and new trends.
- Oracle = the 10 products the hidden model itself would pick. The reference recommender can be beaten.
- Told to us in person: the simulator was written by an AI agent.
- Clarified 14 Nov 17:05 CET: a shopper who already bought a product, organically (`shop.history_events`, `shop.events`) or through our lists, is much less likely to buy it again when we show it. The history and the live organic events were generated without this effect, so repeat purchases seen there mean nothing. Our own feedback follows the rule.
- Changed 14 Nov 16:45 CET: a product that sold out less than 5 s before the request no longer makes the answer invalid. That slot sells nothing.

## Measured

| | Value |
|---|---|
| Baseline, expected conversion per request | 0.64–0.69% |
| Reference | 2.10% |
| Oracle, implied by the hourly scores | about 3.6–3.7% |
| Best team, Saturday 12:26 UTC | 0.90% |
| History carousel: click, purchase | 3.75%, 1.40% |
| Live on best sellers: click, purchase | 2.4%, 0.7–0.9% |

## Working picture

Hidden store state (product appeal, prices, stock, a schedule of new products, price cuts and trends) and hidden shopper state (segment, taste, current session, what they bought) drive: session → request → examine slots → at most one click → buy or not.

```
P(buy | list) ≈ Σ over slots k:  1/log2(k+1)  ×  P(click | shopper, product_k)  ×  P(buy | click, product_k)
```

What drives `P(click | shopper, product)`, strongest first:

1. The product is the one just viewed, or any recent view.
2. The shopper viewed the product on earlier days and did not buy it.
3. Same subcategory as the session, then same category.
4. The shopper's long-term favourite category.
5. Shopper segment × category (at least one segment: Android in the south).
6. Product appeal: subcategory, brand, feature phrases, a product-specific rest.
7. A live trend on the subcategory.

And one strong negative: the shopper already bought the product.

No evidence so far that slots interact. If that holds, the best list is the products sorted by purchase probability.

**History and live are not the same model.** A bought product is a strong positive in the history log and a negative live. Treat every history effect as a prior until seen live.

## Verdicts on the first hypotheses

| Slug | Verdict | Evidence | Consequence |
|---|---|---|---|
| one-click-funnel | **confirmed** | 2M requests: at most one click, purchase is always the clicked product | Model click, then buy after click |
| attention-decay | **confirmed** | One product across slots follows 1/log2(k+1) within 10% | Slots 1–3 carry 47% of the weight |
| slot-independent | **likely**, live probe open | A strong slot 1 does not lower clicks below it (3.99% against 2.80%) | Sort by purchase probability |
| session-intent | **confirmed** | Next organic view: same subcategory 73%, same category 80% | Session features lead |
| last-view | **confirmed** | Slot 1, history: same product 6.7% purchase, same subcategory 0.84%, same category 0.42% | Candidates from recent views first |
| page-matters | **confirmed**, but it is "views or no views" | Home 0.14%, other pages 1.7%. Product and category pages are equal | Two cases: with and without recent views |
| context-effects | **confirmed** for device × region | Android in Andalucía, Canarias, Murcia: 4–14 times better in four categories, history and live, new shoppers too. No effect of hour or day | Segment priors, also for cold shoppers |
| user-persistence | **confirmed** | 16,967 of 16,973 returning live users are in the history | Long-term features for 70% of requests |
| no-rebuy | **confirmed live, opposite in history** | Live: bought before 0.024% per impression, never seen 0.041%, viewed not bought 0.133%. History: bought before 2.30% against 0.12% | Exclude bought products. Do not learn this from history |
| price-sensitivity | **weak** | Under 10 € converts about twice as well as 35–60 €. Not monotone. Price explains 3% of buy-per-view across products | A minor feature |
| price-change | **confirmed, small** | Pets −20%: view share +15%, buy per view +7% | A small boost for repriced products |
| trend-lead | **confirmed as a step** | Two subcategories, views ×5 at a half-hour mark, in `shop.events` at once | Subcategory multiplier from the last 10–15 minutes of views |
| old-policy | **confirmed, and narrower than assumed** | One category per request, not personalised, top 1,000 products take 96% of impressions | The log cannot judge cross-category lists, the home page or rare products |
| text-signal | **confirmed in a simple form** | Descriptions are brand + subcategory + 2 of 20 phrases. Phrases explain 18% of buy-per-view across products | Parse phrases. No embeddings |
| shopper-clusters | **open** | One segment found by device × region. Taste clusters not yet tested | See new hypotheses |

## Variation factors found

Format: `factor · affects · effect size · source`.

- slot · click and buy after click · 1/log2(k+1); buy after click 42% → 31% · attention-decay
- product in recent views · both · ×14 purchase (history) · last-view
- product is the last view · both · 6.7% at slot 1 (history), 4.4% at slots 1–3 (live, 91 impressions) · last-view
- product viewed on earlier days · both · never 0.09%, 3–9 times 1.55%, 10+ times 6.96% (history) · user-persistence
- same subcategory as last view · both · ×2 over same category (history); live no gap yet · session-intent
- same category as last view · both · ×5 over another category (live) · live feedback
- shopper's top category on the home page · both · ×11 (history) · page-matters
- already bought · both · ×0.6 of never-seen and ×0.2 of viewed-not-bought (live) · no-rebuy
- segment Android-south × category · both · Home & Kitchen ×14, Fashion ×7, Computers & Gaming ×5, Electronics ×4, Toys ×2, Books ×1.2, others ×1 · context-effects
- new shopper · both · ×2 on best sellers (live); they own nothing yet · live feedback
- product appeal · both · click rate at slot 1 from 0.18% to 2.26% (5th to 95th percentile) · catalogue
- subcategory, brand, feature phrases · both · half of the variance of popularity and of buy-per-view · text-signal
- category · buy · Books 4.1% down to Pets 0.15% per request (history) · carousel history
- number of recent views · both · 2.06% with one view, 1.39% with six · carousel history
- price · buy · weak, cheap is better · price-sensitivity
- price cut · views and buy · +15% views, +7% buy per view for −20% · price-change
- trend · views · ×5 on the top products of a subcategory · trend-lead
- new product · buy per view · 6.5% against 5.3% · live stream
- stock · validity · out at once, back about a minute late · live stream

## New hypotheses

| Slug | Claim | Test |
|---|---|---|
| bought-penalty | Live, a bought product stays penalised for the whole event, whether bought in history or today | live feedback split by purchase date, probe arm |
| history-differs | Other history effects also change sign or size live (viewed-before, favourite category) | compare each factor on live feedback as data grows |
| reshow-last-view | Showing the product the shopper is looking at converts at 4–7% live | probe: last view at slot 1 |
| cross-category | For a shopper in category A, a favourite from category B beats a mediocre product from A | explore arm, split by relation |
| home-personal | On the home page, the shopper's top categories and viewed-not-bought products beat best sellers by ×5 or more | arm on home requests |
| segments | More hidden segments exist, defined by device × region or by taste | history: purchase rate by device × region × category; cluster users on category shares |
| cold-prior | A new shopper behaves like the average of their device × region segment | live feedback of new shoppers by segment |
| phrase-affinity | Shoppers have tastes for feature phrases (value, luxury, kids) across categories | history: lift of phrase share in a user's purchases |
| brand-affinity | Shoppers repeat brands inside a category | history |
| novelty | New products get a boost beyond what their attributes predict | live views of new products against attribute prediction |
| trend-buy | A trending subcategory also converts better in the carousel, not only in views | live feedback on trend subcategories |
| slot-probe | Shuffling the same list changes only the slot weights | probe arm with shuffled order |
| own-state | Each team has its own shopper state: what we sell today lowers our later scores | compare our expected conversion with the baseline's on the same list |
| final-schedule | The final repeats the practice schedule compressed: new products, a price cut, a trend | Sunday practice hours, then watch `catalog_updates` |
| reference-is | The reference is "recent views, then same category". It is weakest on cold requests | compare our arms with the reference per segment on the leaderboard |

## What would overturn the picture

- Click rate at a slot that depends on what sits above it.
- A live probe where the last viewed product does not convert.
- Our feedback conversion drifting away from the leaderboard number.
- A second effect, besides repeat purchases, with opposite signs in history and live.
- A final with a different mix of pages or segments than the practice.
