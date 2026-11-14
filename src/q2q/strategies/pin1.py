"""Pin 1: ranker2 with today's carts pinned first. For the home route. docs/hypotheses/H-home-who.md.

Live home lists (14 Nov): a product carted today and not bought converts at 0.37% per slot-weighted impression,
a history cart at 0.15% and anything else at 0.07%, inside the same lists. 60% of home requests have one or more
of today's carts and our lists show 22% of them. ranker2 merges history and today's carts, so today's go first here:
most-carted first, ties in ranker2's order, at most PIN of them, then ranker2's list.
"""
from q2q.strategies import ranker2
from q2q.strategy import Strategy

PIN = 3


class Pin1(Strategy):
    name = "pin1"

    def recommend(self, req, state):
        base = ranker2.STRATEGY.recommend(req, state)
        shopper = state.shopper(req.user_id)
        bought = shopper.bought if shopper else ()
        carts = {p: n for p, n in state.today_carts(req.user_id).items()
                 if p not in bought and p in state.products and state.available(p)}
        order = {p: i for i, p in enumerate(base)}
        pinned = sorted(carts, key=lambda p: (-carts[p], order.get(p, len(base)), p))[:PIN]
        return (pinned + [p for p in base if p not in pinned])[:10]


STRATEGY = Pin1()
