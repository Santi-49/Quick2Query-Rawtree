"""Ranker 7: ranker2 with a purchase model fitted on the organic stream (q2q.train7) instead of our ~1,000 purchases.

ranker7_buy predicts that a shopper buys a product later today after viewing it, from ranker2's features as of the
view (slot and page fixed). Score = P(click) x P(buy | click)^(1 - ALPHA) x P(organic buy | view)^ALPHA x trend x
price cut, with ranker2's click and buy models. ALPHA = 1 drops ranker2's buy model; 0.5 is the geometric blend.
Until all three model files exist it answers like ranker2.
"""
import lightgbm as lgb
import numpy as np

from q2q import rt
from q2q.strategies import ranker2
from q2q.strategy import Strategy

BUY_MODEL = rt.ROOT / "models" / "ranker7_buy.txt"
ALPHA = 0.5


class Ranker7(Strategy):
    name = "ranker7"

    def __init__(self, alpha: float = ALPHA):
        self.alpha, self.models, self.mtimes = alpha, None, None

    def recommend(self, req, state):
        paths = (ranker2.MODEL, ranker2.BUY_MODEL, BUY_MODEL)
        mtimes = tuple(m.stat().st_mtime if m.exists() else None for m in paths)
        if mtimes != self.mtimes:
            self.models = tuple(lgb.Booster(model_file=str(m)) for m in paths) if all(mtimes) else None
            self.mtimes = mtimes
        if self.models is None:
            return ranker2.STRATEGY.recommend(req, state)
        c = ranker2.context(req, state)
        cands = ranker2.candidates(state, c)
        if not cands:
            return []
        X = np.array([ranker2.features(p, 1, req, c) for p in cands], dtype=float)
        click, buy, organic = (m.predict(X, num_threads=1) for m in self.models)
        score = click * buy ** (1 - self.alpha) * organic ** self.alpha
        scored = sorted(((float(s) * state.trend.get(p.subcategory, 1.0) * (2 - state.price_cut.get(p.id, 1.0)), p.id)
                         for s, p in zip(score, cands)), reverse=True)
        return [pid for _, pid in scored[:10]]


STRATEGY = Ranker7()
