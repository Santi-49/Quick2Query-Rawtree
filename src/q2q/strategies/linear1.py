"""Linear 1: a log-linear score on clean 0/1 indicators, fitted by logistic regression (eda/linear/fit.py).

Hypothesis H-loglinear: the simulator multiplies base appeal by a few clean factors. Score at slot 1 =
exp(sum of click coefficients) x P(purchase | click) x trend. Candidates as ranker2. Bought products are never shown.
Coefficients come from models/linear1.json; until it exists it answers like rules4.

State fields read with getattr, off when missing:
- state.our_clicks_today: user -> set of products clicked through our lists today and not bought.
"""
import json
import math

import numpy as np

from q2q import rt
from q2q.strategies import ranker2, rules4
from q2q.strategy import Strategy

COEFS = rt.ROOT / "models" / "linear1.json"
NAMES = [f"slot{k}" for k in range(2, 11)] + [
    "log_appeal", "in_views", "first_view", "main_cat", "same_sub_any", "carted", "carted2", "viewed_only", "bought_today",
    "viewed_today", "sub_today", "top1_cat", "top2_cat", "top3_cat", "other_cat", "phrase_22_30", "phrase_30_38", "phrase_38",
    "brand_match", "coview", "price_cut", "new_product", "new_shopper", "page_home", "page_category", "our_click_today",
    "carted_x_high_cart", "in_views_x_category"]


def context(req, state, live: bool = True, today=None, our_clicks=None, bought_today=(), cut: dict | None = None,
            cart_high: float = 0.05) -> dict:
    """ranker2.context plus category ranks, recent brands and the first view. Training passes the request-time values
    of today's views, our clicks, today's purchases and price cuts; serving reads them from the State."""
    c = ranker2.context(req, state, live=live, today=today)
    s = c["shopper"]
    if our_clicks is None:
        our_clicks = (getattr(state, "our_clicks_today", None) or {}).get(req.user_id, set())
    ranked = sorted(c["shares"], key=c["shares"].get, reverse=True)
    distinct = list(dict.fromkeys(v.id for v in c["views"]))
    c.update(rank={cat: i for i, cat in enumerate(ranked)}, brands={v.brand for v in c["views"]}, first1=distinct[0] if distinct else None,
             our=our_clicks, bought_today=set(bought_today), cut=state.price_cut if cut is None else cut,
             high_cart=bool(s and s.cart_rate >= cart_high))
    return c


def indicators(p, slot: int, req, c: dict) -> list[float]:
    s, known = c["shopper"], c["known"]
    carted = s.carted.get(p.id, 0) if s else 0
    rank = c["rank"].get(p.category)
    ph = sum(s.phrase_share.get(f, 0.0) for f in p.phrases) if known else 0.0
    in_views = p.id in c["ids"]
    return [slot == k for k in range(2, 11)] + [
        math.log(p.appeal), in_views, p.id == c["first1"], p.category == c["main"], p.subcategory in c["subs"],
        carted > 0, carted > 1, p.id in c["viewed"] and not carted, p.id in c["bought_today"],
        p.id in c["today"], p.subcategory in c["today_subs"],
        rank == 0, rank == 1, rank == 2, rank is not None and rank > 2,
        0.22 < ph <= 0.30, 0.30 < ph <= 0.38, ph > 0.38,
        p.brand in c["brands"] and not in_views, c["co"].get(p.id, 0) > 0, c["cut"].get(p.id, 1.0) < 1, p.is_new,
        req.is_new_user, req.page == "home", req.page == "category", p.id in c["our"],
        carted > 0 and c["high_cart"], in_views and req.page == "category"]


class Linear1(Strategy):
    name = "linear1"

    def __init__(self):
        self.model, self.mtime = None, None

    def recommend(self, req, state):
        mtime = COEFS.stat().st_mtime if COEFS.exists() else None
        if mtime != self.mtime:
            self.model, self.mtime = (json.loads(COEFS.read_text(encoding="utf-8")) if mtime else None), mtime
        if self.model is None:
            return rules4.STRATEGY.recommend(req, state)
        m = self.model
        c = context(req, state, cart_high=m["cart_rate_high"])
        cands = ranker2.candidates(state, c)
        if not cands:
            return []
        X = np.array([indicators(p, 1, req, c) for p in cands], dtype=float)
        click = X @ np.array(m["click"]) + m["click_intercept"]
        buy = 1 / (1 + np.exp(-(X @ np.array(m["buy"]) + m["buy_intercept"])))
        scored = sorted(((math.exp(k) * b * state.trend.get(p.subcategory, 1.0), p.id) for k, b, p in zip(click, buy, cands)), reverse=True)
        return [pid for _, pid in scored[:10]]


STRATEGY = Linear1()
