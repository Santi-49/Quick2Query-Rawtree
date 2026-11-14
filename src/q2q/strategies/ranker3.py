"""Ranker 3: ranker2 plus what was found after it (H-gap, H-loglinear), trained by q2q train3.

Added inputs, all as of the request: today's carts in the live stream (times, minutes since, same category and
subcategory), our own list clicked earlier today and not bought, a one-view session, distinct recent views, log
appeal, log buys per view, and history cart x high cart rate. carted_not_bought is history only, as in training.
Every product carted today (not bought, in stock) is a candidate.

Score = P(click at slot 1) x P(purchase | click) x CART_PRIOR if carted today x trend x price cut.
Until both model files exist it answers like ranker2.

State read with getattr, off when missing:
- state.today_cart_last(user_id) -> {product: epoch seconds of the latest cart today}
- state.our_clicks_today: user -> set of products clicked through our lists today and not bought.
"""
import math

import lightgbm as lgb

from q2q import rt
from q2q.strategies import ranker2
from q2q.strategy import Strategy

MODEL = rt.ROOT / "models" / "ranker3.txt"
BUY_MODEL = rt.ROOT / "models" / "ranker3_buy.txt"
FEATURES = ranker2.FEATURES + ["carted_today", "mins_since_cart_today", "cat_carted_today", "sub_carted_today", "clicked_ours_today",
                               "single_view_session", "n_recent_views", "log_appeal", "log_bpv", "cart_x_high_cart_rate"]
CARTED = ranker2.FEATURES.index("carted_not_bought")
CART_PRIOR = 1.0        # multiplier on a today-cart's score; 1 = the trees learnt it (train3 reports the rows)
CART_AGE = 60.0         # minutes since a today cart when the State has no cart times
HIGH_CART = 0.08        # shopper cart rate above which a history cart counts (H-loglinear: x2.5 on clicks)
BPV_PRIOR, BPV_N = 3.4, 20.0  # smoothing of buys per view, as rules5
NAN = math.nan


def context(req, state, live: bool = True, today: list[str] | None = None, carts: dict | None = None, cart_last: dict | None = None,
            our: set | None = None, bought_today=()) -> dict:
    """ranker2.context plus today's carts and our clicks. Training passes their request-time values (live=False);
    serving reads them from the State."""
    c = ranker2.context(req, state, live=live, today=today)
    if carts is None:
        carts = state.today_carts(req.user_id)
        cart_last = (getattr(state, "today_cart_last", None) or (lambda u: {}))(req.user_id)
        our = (getattr(state, "our_clicks_today", None) or {}).get(req.user_id, set())
    s = c["shopper"]
    bought = set(c["bought"]) | set(bought_today)
    hist = dict(s.carted) if s else {}
    if live:  # the live Shopper's carts include today's
        hist = {p: n - carts.get(p, 0) for p, n in hist.items() if n - carts.get(p, 0) > 0}
    tc = {p: n for p, n in carts.items() if p not in bought}
    products = state.products
    cats, subs = {}, {}
    for p in tc:
        if p in products:
            cats[products[p].category] = cats.get(products[p].category, 0) + 1
            subs[products[p].subcategory] = subs.get(products[p].subcategory, 0) + 1
    c.update(bought=bought, hist=hist, tc=tc, cart_last=cart_last or {}, tc_cats=cats, tc_subs=subs, our={p for p in (our or ()) if p not in bought},
             n_distinct=len({v.id for v in c["views"]}), high_cart=bool(s and c["known"] and s.cart_rate >= HIGH_CART))
    return c


def features(p, slot: int, req, c: dict) -> list[float]:
    row = ranker2.features(p, slot, req, c)
    hist = c["hist"].get(p.id, 0)
    row[CARTED] = min(hist, 3)
    n = c["tc"].get(p.id, 0)
    last = c["cart_last"].get(p.id)
    own = 1 if n else 0
    return row + [
        min(n, 3),
        (max(0.0, req.ts - last) / 60 if last else CART_AGE) if n else NAN,
        c["tc_cats"].get(p.category, 0) - own,
        c["tc_subs"].get(p.subcategory, 0) - own,
        p.id in c["our"],
        c["n_distinct"] == 1,
        c["n_distinct"],
        math.log(p.appeal) if p.appeal > 0 else NAN,
        math.log((p.buys + BPV_PRIOR) / (p.views + BPV_N)),
        hist > 0 and c["high_cart"]]


def candidates(state, c: dict) -> list:
    """ranker2's candidates plus every product carted today (not bought, in stock)."""
    out = {p.id: p for p in ranker2.candidates(state, c)}
    for pid in c["tc"]:
        if pid not in out and pid in state.products and state.available(pid):
            out[pid] = state.products[pid]
    return list(out.values())


class Ranker3(Strategy):
    name = "ranker3"

    def __init__(self):
        self.models, self.mtimes = None, None

    def recommend(self, req, state):
        mtimes = tuple(m.stat().st_mtime if m.exists() else None for m in (MODEL, BUY_MODEL))
        if mtimes != self.mtimes:
            self.models = tuple(lgb.Booster(model_file=str(m)) for m in (MODEL, BUY_MODEL)) if all(mtimes) else None
            self.mtimes = mtimes
        if self.models is None:
            return ranker2.STRATEGY.recommend(req, state)
        c = context(req, state)
        cands = candidates(state, c)
        if not cands:
            return []
        X = [features(p, 1, req, c) for p in cands]
        click, buy = (m.predict(X) for m in self.models)
        scored = sorted(((float(k) * float(b) * (CART_PRIOR if p.id in c["tc"] else 1.0) * state.trend.get(p.subcategory, 1.0)
                          * (2 - state.price_cut.get(p.id, 1.0)), p.id) for k, b, p in zip(click, buy, cands)), reverse=True)
        return [pid for _, pid in scored[:10]]


STRATEGY = Ranker3()
