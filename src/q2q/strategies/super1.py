"""Super 1: every live signal of the two fresh-eyes studies (15 Nov) stacked on ranker2's scores.

Multipliers on P(click) x P(buy | click) x trend x price cut:
- the shopper's live purchase share of the category (aff1): 0.5 + 3.5 x share, 0.5 if they bought elsewhere only;
- in the last viewed category: x BOOST (lock3);
- the subcategory's live purchases over what the slots predicted, 6 h of our feedback, shrunk and clipped 0.2-2.5;
- the product's organic purchases per hour, last 3 h against the 21 h before, clipped 0.7-2.5.
The two tables are refreshed every REFRESH seconds in a background thread, so a request never waits on SQL.
Candidates: ranker2's, the top products of the last viewed category and of each category bought live. Label: hash.
Home page: today's organic views from shop.events stand in for the missing recent views.
"""
import threading
import time
from dataclasses import replace

from q2q import rt
from q2q.strategies import ranker2
from q2q.strategy import Strategy

BOOST, EXTRA, REFRESH = 2.0, 30, 600
SLOTS = """WITH f AS (SELECT shown::Array(String) AS s, purchased::String AS b FROM {TEAM}.feedback
                   WHERE ts::DateTime64(3) > now() - INTERVAL 6 HOUR AND length(shown::Array(String)) = 10)
SELECT p, sum(y) AS buys, sum(r) AS expected FROM (
  SELECT p, i, y, avg(y) OVER (PARTITION BY i) AS r FROM (SELECT p, i, toUInt8(b = p) AS y FROM f ARRAY JOIN s AS p, arrayEnumerate(s) AS i))
GROUP BY p"""
HOURLY = """SELECT product_id::String AS p, countIf(ts::DateTime64(3) > now() - INTERVAL 3 HOUR) / 3 AS recent,
       countIf(ts::DateTime64(3) <= now() - INTERVAL 3 HOUR) / 21 AS before
FROM shop.events WHERE event_type::String = 'purchase' AND ts::DateTime64(3) > now() - INTERVAL 24 HOUR GROUP BY p"""


def clip(x, lo, hi):
    return min(hi, max(lo, x))


class Super1(Strategy):
    name = "super1"

    def __init__(self):
        self.sub, self.hot, self.built, self.busy = {}, {}, 0.0, False

    def _refresh(self, state):
        try:
            buys, expected = {}, {}
            for r in rt.query(SLOTS.replace("{TEAM}", rt.TEAM)):
                p = state.products.get(r["p"])
                if p:
                    buys[p.subcategory] = buys.get(p.subcategory, 0) + float(r["buys"])
                    expected[p.subcategory] = expected.get(p.subcategory, 0) + float(r["expected"])
            self.sub = {s: clip((buys[s] + 5) / (expected[s] + 5), 0.2, 2.5) for s in buys}
            self.hot = {r["p"]: clip((float(r["recent"]) + 3) / (float(r["before"]) + 3), 0.7, 2.5) for r in rt.query(HOURLY)}
        finally:
            self.built, self.busy = time.time(), False

    def recommend(self, req, state):
        if time.time() - self.built > REFRESH and not self.busy:
            self.busy = True
            threading.Thread(target=self._refresh, args=(state,), daemon=True).start()
        base = ranker2.STRATEGY
        if base.models is None:   # ranker2 loads its models on its first call
            return base.recommend(req, state)
        return self.rank(req, state, state.today_views(req.user_id), state._live.get(req.user_id, ()))

    def rank(self, req, state, today, bought):
        """today: products viewed earlier today, newest last; bought: products bought live."""
        base = ranker2.STRATEGY
        if not req.views:   # home page: today's organic views from shop.events stand in for the recent views (lock2)
            today = [p for p in today if p in state.products][-5:]
            if today:
                req = replace(req, views=today)
        live = [state.products[p].category for p in bought if p in state.products]
        share = {cat: live.count(cat) / len(live) for cat in set(live)}
        c = ranker2.context(req, state)
        last = c["views"][-1].category if c["views"] else None
        cands = {p.id: p for p in ranker2.candidates(state, c)}
        for cat, n in [(last, EXTRA)] + [(cat, 5) for cat in share]:
            for pid in state.by_category.get(cat, ())[:n]:
                if pid not in cands and pid not in c["bought"] and state.available(pid):
                    cands[pid] = state.products[pid]
        cands = list(cands.values())
        if not cands:
            return []
        X = [ranker2.features(p, 1, req, c) for p in cands]
        click, buy = (m.predict(X) for m in base.models)
        scored = []
        for k, b, p in zip(click, buy, cands):
            s = float(k) * float(b) * state.trend.get(p.subcategory, 1.0) * (2 - state.price_cut.get(p.id, 1.0))
            if live:
                s *= 0.5 + 3.5 * share[p.category] if p.category in share else 0.5
            if p.category == last:
                s *= BOOST
            s *= self.sub.get(p.subcategory, 1.0) * self.hot.get(p.id, 1.0)
            scored.append((s, p.id))
        return [pid for _, pid in sorted(scored, reverse=True)[:10]]


STRATEGY = Super1()
