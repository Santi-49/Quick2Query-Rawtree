"""Ranker 8: ranker3's inputs minus the groups the ablation found to be noise, plus rules5's rank of the candidate
(docs/hypotheses/H-ablation.md), trained by train8 with more regularisation.

Score = P(click at slot 1) x P(purchase | click) x trend x price cut (each multiplier on if TREND / PRICE_CUT).
Candidates: ranker3's plus rules5's top 10. Until both model files exist it answers like ranker2.
Reads only what the live State has: today_carts, today_views, shopper, segment, trend, price_cut, coview.
ranker3.context reads today_cart_last / our_clicks_today with getattr; both are absent live, so ranker8 drops
the two inputs built on them.
"""
import lightgbm as lgb

from q2q import rt
from q2q.strategies import ranker2, ranker3, rules5
from q2q.strategy import Strategy

MODEL = rt.ROOT / "models" / "ranker8.txt"
BUY_MODEL = rt.ROOT / "models" / "ranker8_buy.txt"
ALL = ranker3.FEATURES + ["rules5_rank"]
DROP = ["mins_since_cart_today", "clicked_ours_today",  # not on the live State (and noise in the ablation)
        "slot",                                       # dropping it gained main hit3 +5.3 ± 1.8
        "coview",                                     # dropping it gained new-shopper hit3 +4.3 ± 1.6
        "price", "n_views", "single_view_session", "n_recent_views", "viewed_today", "sub_viewed_today"]  # noise
FEATURES = [f for f in ALL if f not in DROP]
COLS = [ALL.index(f) for f in FEATURES]
R5_OUT = 11      # rules5_rank of a product outside rules5's top 10
TREND, PRICE_CUT = False, False  # both within one se of nothing in the ablation (no price cut active at all)


def rules5_ranks(req, state) -> dict[str, int]:
    return {pid: i for i, (_, pid, _) in enumerate(rules5.STRATEGY.explain(req, state), 1)}


def full_row(p, req, c: dict, r5: dict, slot: int = 1) -> list[float]:
    """Every input of ALL; the model reads COLS."""
    return ranker3.features(p, slot, req, c) + [r5.get(p.id, R5_OUT)]


class Ranker8(Strategy):
    name = "ranker8"

    def __init__(self):
        self.models, self.mtimes = None, None

    def recommend(self, req, state):
        mtimes = tuple(m.stat().st_mtime if m.exists() else None for m in (MODEL, BUY_MODEL))
        if mtimes != self.mtimes:
            self.models = tuple(lgb.Booster(model_file=str(m)) for m in (MODEL, BUY_MODEL)) if all(mtimes) else None
            self.mtimes = mtimes
        if self.models is None:
            return ranker2.STRATEGY.recommend(req, state)
        c = ranker3.context(req, state)
        r5 = rules5_ranks(req, state)
        cands = {p.id: p for p in ranker3.candidates(state, c)}
        for pid in r5:
            if pid not in cands and pid not in c["bought"] and pid in state.products:
                cands[pid] = state.products[pid]
        if not cands:
            return []
        cands = list(cands.values())
        X = [[row[i] for i in COLS] for row in (full_row(p, req, c, r5) for p in cands)]
        click, buy = (m.predict(X) for m in self.models)
        scored = sorted(((float(k) * float(b) * (state.trend.get(p.subcategory, 1.0) if TREND else 1.0)
                          * ((2 - state.price_cut.get(p.id, 1.0)) if PRICE_CUT else 1.0), p.id) for k, b, p in zip(click, buy, cands)), reverse=True)
        return [pid for _, pid in scored[:10]]


STRATEGY = Ranker8()
