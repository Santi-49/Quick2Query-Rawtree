"""Lock 2: the home page answered as if today's organic views were the request's recent views, then lock1.

Home requests carry no recent views, but most of those shoppers have organic events earlier today. Simulator view:
a session's intent is a category; the last product they looked at today is the best guess of it. No views today:
ranker2. Label: the hash name, so the router needs no restart.
"""
from dataclasses import replace

from q2q.strategies import lock1, ranker2
from q2q.strategy import Strategy

LAST = 5   # today's views used, newest last


class Lock2(Strategy):
    name = "lock2"

    def recommend(self, req, state):
        today = [p for p in state.today_views(req.user_id) if p in state.products][-LAST:]
        if req.views or not today:
            return ranker2.STRATEGY.recommend(req, state)
        return lock1.STRATEGY.recommend(replace(req, views=today), state)


STRATEGY = Lock2()
