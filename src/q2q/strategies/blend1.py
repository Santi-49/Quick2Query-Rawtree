"""Blend 1: rank fusion of ranker2 and rules5.

Two different models of the same shopper: a product both put high goes first (reciprocal rank fusion of the two
top-10 lists). docs/hypotheses/H-blend.md.
"""
from q2q.strategies import ranker2, rules5
from q2q.strategy import Strategy

K = 10.0   # rank damping: larger = flatter
W = {"ranker2": 1.0, "rules5": 0.6}


class Blend1(Strategy):
    name = "blend1"

    def recommend(self, req, state):
        score = {}
        for name, s in (("ranker2", ranker2.STRATEGY), ("rules5", rules5.STRATEGY)):
            for i, pid in enumerate(s.recommend(req, state)):
                score[pid] = score.get(pid, 0.0) + W[name] / (K + i)
        return sorted(score, key=score.get, reverse=True)[:10]


STRATEGY = Blend1()
