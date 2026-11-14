# What we built, in plain words

## The problem

A simulated online shop sends us three shoppers every second. For each one we have three seconds to pick 10 products for a carousel. The shopper may click one and may buy it. A hidden model decides how likely that is, and our score is how close our 10 products come to the 10 that model would have picked itself.

We never see the hidden model. We only see what the shop shows us: who the shopper is, what they looked at in the last minutes, what happened to our past answers, and a public leaderboard.

## The idea

We do not try to copy the hidden model. We ask it questions.

1. **We look at the data** and write down what seems to matter. For example: a shopper looking at jeans mostly wants more fashion.
2. **We turn each belief into a hypothesis** with a test: one sentence that can be proven wrong, and the numbers that would prove it.
3. **We build a strategy from the beliefs that survived.** A strategy is one small file that scores products for a shopper.
4. **We let strategies compete on live traffic**, ten minutes each, and keep the winner.

Everything we learn goes into one page, `docs/SIMULATOR.md`. Strategies are built from that page, so every line of a strategy has a reason we can point to.

## The pieces

- **The router** is the only program that answers shoppers. Every fraction of a second it reads the new requests, decides which strategy answers each one, checks the answer and sends it.
- **The state** is what the router knows right now: the catalogue, what is out of stock, what is trending in the last 15 minutes, what each shopper bought and viewed, and what each kind of shopper tends to like.
- **A strategy** turns one request and the state into 10 products. `baseline` shows the best sellers. `rules` multiplies a handful of effects we measured. `explore` shows products at random from six chosen groups.
- **The guard** stands between a strategy and the shop. It removes anything out of stock or repeated and fills the gaps with best sellers. A broken experiment cannot produce an invalid answer.
- **`arms.toml`** is the one switch. It says which strategy owns which 10-minute block and how many shoppers go to the explore arm. Changing it takes effect within a second, with no restart.
- **RawTree** is the memory. Features are SQL run there, and everything we track is stored there: leaderboard readings, block results, explore logs, the lease.

## How one answer is made

A shopper on a product page has looked at two pairs of smartwatches. The `rules` strategy collects candidates: those two products, other smartwatches, other electronics, things this shopper viewed on earlier days, and the favourites of shoppers like them. Each candidate gets a score:

```
score = appeal of the product
      × how close it is to what the shopper is doing now
      × whether they looked at it before
      × how much they like its category
      × how much their device and region like its category
      × whether its subcategory is trending
      × whether its price was just cut
```

Products the shopper already bought are removed. The 10 highest scores are the answer, best first, because shoppers look at the first slots much more than the last.

Each multiplier is an effect size we measured. The product being looked at converts about 35 times better than a product from another category, so its multiplier is 35.

## How we know what works

Clicks and purchases on our own answers are too rare to compare two strategies quickly: about 75 purchases an hour over all traffic.

The leaderboard gives an exact number, but for the whole last hour. We noticed that two readings ten minutes apart differ only by the ten minutes that entered and the ten that left. Subtracting them gives our result for a single 10-minute block, and the same subtraction for the baseline team gives the comparison on the very same shoppers.

So strategies take turns: `rules`, `baseline`, `rules`, `baseline`. After a few turns we know which one is better and by how much. A challenger becomes champion after winning three pairs of blocks.

## Why a small part of the traffic is random

The shop's old logs only show what the old carousel showed: popular products from one category. They cannot tell us what happens when we show a shopper something from another category, or a brand-new product. The explore arm shows a few shoppers products we would not normally pick, from six groups, and records the chance each product had of being shown. That is how we measure what the logs cannot.

## What must never happen

- Two programs answering at once. A lease in RawTree stops a second router from starting.
- An invalid answer. The guard prevents it.
- A strategy that only works on the practice shoppers. The final has new shoppers, new products and new trends, so strategies score products by their attributes and shoppers by their session and segment. What we remember about a particular shopper is a bonus.
