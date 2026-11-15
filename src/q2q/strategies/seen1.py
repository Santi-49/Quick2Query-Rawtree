"""Seen 1: the last two viewed products (newest first) in slots 1-2, then ranker2's list.

Live feedback, last 6 h (fresh-eyes study, 15 Nov): just-viewed products convert 0.87% per top-3 impression against
0.58% for same-category items, yet lists show 0.37 of them on average. Bought or unavailable products are skipped
(the simulator suppresses repeat purchases). Label: the hash name, so the router needs no restart.
"""
from q2q.strategies import ranker2
from q2q.strategy import Strategy

PIN = 2


class Seen1(Strategy):
    name = "seen1"

    def recommend(self, req, state):
        base = ranker2.STRATEGY.recommend(req, state)
        shopper = state.shopper(req.user_id)
        bought = shopper.bought if shopper else ()
        pinned = []
        for p in reversed(req.views):
            if p not in pinned and p not in bought and p in state.products and state.available(p):
                pinned.append(p)
            if len(pinned) == PIN:
                break
        return (pinned + [p for p in base if p not in pinned])[:10]


STRATEGY = Seen1()
