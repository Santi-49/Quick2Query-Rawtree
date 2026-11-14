"""Ranker 6: ranker2's features and candidates, each model an average of several LightGBM boosters (q2q.train6).

Score = mean P(click at slot 1) x mean P(purchase | click) x trend x price cut, as ranker2.
Models: models/ranker6_click_<i>.txt and models/ranker6_buy_<i>.txt, any number of each.
Until both kinds exist it answers like ranker2.
"""
import lightgbm as lgb
import numpy as np

from q2q import rt
from q2q.strategies import ranker2
from q2q.strategy import Strategy

DIR = rt.ROOT / "models"


def files() -> tuple[list, list]:
    return sorted(DIR.glob("ranker6_click_*.txt")), sorted(DIR.glob("ranker6_buy_*.txt"))


def mean_predict(models, X) -> np.ndarray:
    return np.mean([m.predict(X, num_threads=1) for m in models], axis=0)


class Ranker6(Strategy):
    name = "ranker6"

    def __init__(self):
        self.models, self.mtimes = None, None

    def recommend(self, req, state):
        click, buy = files()
        mtimes = tuple((f.name, f.stat().st_mtime) for f in click + buy)
        if mtimes != self.mtimes:
            self.models = ([lgb.Booster(model_file=str(f)) for f in click], [lgb.Booster(model_file=str(f)) for f in buy]) if click and buy else None
            self.mtimes = mtimes
        if self.models is None:
            return ranker2.STRATEGY.recommend(req, state)
        c = ranker2.context(req, state)
        cands = ranker2.candidates(state, c)
        if not cands:
            return []
        X = np.array([ranker2.features(p, 1, req, c) for p in cands], dtype=float)
        k, b = (mean_predict(m, X) for m in self.models)
        scored = sorted(((float(x) * float(y) * state.trend.get(p.subcategory, 1.0) * (2 - state.price_cut.get(p.id, 1.0)), p.id)
                         for x, y, p in zip(k, b, cands)), reverse=True)
        return [pid for _, pid in scored[:10]]


STRATEGY = Ranker6()
