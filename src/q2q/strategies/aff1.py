"""Affinity 1: ranker2's scores times the shopper's purchase share of the product's category in the live stream.

Second fresh-eyes study (15 Nov, 6 h of feedback, purchases over what the slot predicts): for shoppers with 3+ live
purchases, in-category items go from 0.64 (share 0) to 4.26 (share >= 0.75), monotone; among shoppers who bought
today, items in a category they did not buy in convert at about 0.4-0.5. Read as a hidden per-shopper category taste
that also drives their organic purchases. Factor: 0.5 + 3.5 x share if share > 0, 0.5 if they bought elsewhere only,
1 if no live purchases. The top products of each bought category join the candidates. Live purchases are read from
the state's private set so the router needs no restart. Label: the hash name.
"""
from q2q.strategies import ranker2
from q2q.strategy import Strategy

EXTRA = 5   # top products of each bought category added to the candidates


class Aff1(Strategy):
    name = "aff1"

    def recommend(self, req, state):
        base = ranker2.STRATEGY
        live = [state.products[p].category for p in state._live.get(req.user_id, ()) if p in state.products]
        if not live or base.models is None:   # ranker2 loads its models on its first call
            return base.recommend(req, state)
        share = {cat: live.count(cat) / len(live) for cat in set(live)}
        c = ranker2.context(req, state)
        cands = {p.id: p for p in ranker2.candidates(state, c)}
        for cat in share:
            for pid in state.by_category.get(cat, ())[:EXTRA]:
                if pid not in cands and pid not in c["bought"] and state.available(pid):
                    cands[pid] = state.products[pid]
        cands = list(cands.values())
        X = [ranker2.features(p, 1, req, c) for p in cands]
        click, buy = (m.predict(X) for m in base.models)
        scored = sorted(((float(k) * float(b) * state.trend.get(p.subcategory, 1.0) * (2 - state.price_cut.get(p.id, 1.0))
                          * (0.5 + 3.5 * share[p.category] if p.category in share else 0.5), p.id)
                         for k, b, p in zip(click, buy, cands)), reverse=True)
        return [pid for _, pid in scored[:10]]


STRATEGY = Aff1()
