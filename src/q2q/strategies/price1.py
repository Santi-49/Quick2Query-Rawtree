"""Price 1: ranker2's scores times (1 + WEIGHT x the product's price percentile in its category).

Live feedback, last 6 h (fresh-eyes study, 15 Nov): among same-category items in the top 3 slots, the priciest quarter
of a category converts 1.07% per impression against 0.55% for the cheapest, yet ranker2 shows 3.6 times more of the
cheapest. Observational and mixed (the old carousel log is U-shaped), so this is a live test. Also helps the
revenue tie-breaker. Label: the hash name, so the router needs no restart.
"""
import bisect
import time

from q2q.strategies import ranker2
from q2q.strategy import Strategy

WEIGHT = 0.5
REFRESH = 300   # seconds between rebuilds of the category price lists (prices change in catalog updates)


class Price1(Strategy):
    name = "price1"

    def __init__(self):
        self.prices, self.built = {}, 0.0

    def pct(self, p, state) -> float:
        if time.time() - self.built > REFRESH:
            prices = {}
            for q in state.products.values():
                prices.setdefault(q.category, []).append(q.price)
            self.prices = {c: sorted(v) for c, v in prices.items()}
            self.built = time.time()
        v = self.prices.get(p.category)
        return bisect.bisect_left(v, p.price) / len(v) if v else 0.5

    def recommend(self, req, state):
        base = ranker2.STRATEGY
        if base.models is None:   # ranker2 loads its models on its first call
            return base.recommend(req, state)
        c = ranker2.context(req, state)
        cands = ranker2.candidates(state, c)
        if not cands:
            return []
        X = [ranker2.features(p, 1, req, c) for p in cands]
        click, buy = (m.predict(X) for m in base.models)
        scored = sorted(((float(k) * float(b) * state.trend.get(p.subcategory, 1.0) * (2 - state.price_cut.get(p.id, 1.0))
                          * (1 + WEIGHT * self.pct(p, state)), p.id) for k, b, p in zip(click, buy, cands)), reverse=True)
        return [pid for _, pid in scored[:10]]


STRATEGY = Price1()
