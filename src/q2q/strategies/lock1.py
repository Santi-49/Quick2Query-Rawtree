"""Lock 1: ranker2's scores, but the row is filled from the last-viewed product's category first.

Live feedback, last 6 h (fresh-eyes study, 15 Nov): 45% of our slots are off the last view's category and convert at
half the rate; lists with 9-10 items in that category convert 4.1% against 1.1% for 0-4, inside each session-focus
stratum. Candidates: ranker2's plus the category's top products. In-category by ranker2 score, then the rest.
Without views or models it answers like ranker2.
"""
from q2q.strategies import ranker2
from q2q.strategy import Strategy

EXTRA = 60   # top products of the locked category added to the candidates


class Lock1(Strategy):
    name = "lock1"

    def recommend(self, req, state):
        base = ranker2.STRATEGY
        c = ranker2.context(req, state)
        if not c["views"] or base.models is None:   # ranker2 loads its models on its first call
            return base.recommend(req, state)
        cat = c["views"][-1].category
        cands = {p.id: p for p in ranker2.candidates(state, c)}
        for pid in state.by_category.get(cat, ())[:EXTRA]:
            if pid not in cands and pid not in c["bought"] and state.available(pid):
                cands[pid] = state.products[pid]
        cands = list(cands.values())
        X = [ranker2.features(p, 1, req, c) for p in cands]
        click, buy = (m.predict(X) for m in base.models)
        scored = sorted(((float(k) * float(b) * state.trend.get(p.subcategory, 1.0) * (2 - state.price_cut.get(p.id, 1.0)), p.category == cat, p.id)
                         for k, b, p in zip(click, buy, cands)), reverse=True)
        inside = [pid for _, ok, pid in scored if ok]
        return (inside + [pid for _, ok, pid in scored if not ok])[:10]


STRATEGY = Lock1()
