"""Ranker 2: the ranker's 21 inputs plus the signals of the wide-feature study, and a purchase model (q2q train2).

Added inputs (docs/findings/08-ml-patterns.md, last section; H-session-shape, H-reshow-rank, H-home-ceiling):
phrase taste, phrase overlap with the session, carted not bought, organic co-views from the recent views, the
shopper's cart rate, carts in the category, brand and subcategory shares, first or later recent view, the
session's main category, and products / subcategories viewed earlier today.

Score = P(click at slot 1) x P(purchase | click) x trend x price cut. Bought products are never shown.
Until both model files exist it answers like rules4.
"""
import math

import lightgbm as lgb

from q2q import rt
from q2q.strategies import ranker, rules4
from q2q.strategies.rules4 import main_category
from q2q.strategy import Strategy

MODEL = rt.ROOT / "models" / "ranker2.txt"
BUY_MODEL = rt.ROOT / "models" / "ranker2_buy.txt"
FEATURES = ranker.FEATURES + ["phrase_share", "session_phrase_overlap", "carted_not_bought", "coview", "shopper_cart_rate", "cat_carts",
                              "brand_share", "sub_share", "is_first_view", "is_later_view", "in_main_cat", "viewed_today", "sub_viewed_today"]
TOP = ranker.TOP
NAN = math.nan


def context(req, state, live: bool = True, today: list[str] | None = None) -> dict:
    """ranker.context plus the shopper's history shares, the session's phrases and co-views, and today's views.
    today overrides state.today_views (training: the views before the request)."""
    c = ranker.context(req, state, live_purchases=live)
    s = state.shopper(req.user_id, live=live)
    views = c["views"]
    phrases, co, counts = {}, {}, {}
    for v in views:
        counts[v.id] = counts.get(v.id, 0) + 1
        for f in v.phrases:
            phrases[f] = phrases.get(f, 0) + 1
        for b, n in state.coview.get(v.id, {}).items():
            co[b] = co.get(b, 0) + n
    distinct = list(dict.fromkeys(v.id for v in views))
    own = set(req.views)
    seen_today = [p for p in (state.today_views(req.user_id) if today is None else today) if p not in own]
    c.update(shopper=s, known=bool(s and s.cat_share), phrases=phrases, co=co, counts=counts, first=distinct[0] if len(distinct) > 1 else None,
             later=set(distinct[1:]), main=main_category(views), today=set(seen_today),
             today_subs={state.products[p].subcategory for p in seen_today if p in state.products})
    return c


def features(p, slot: int, req, c: dict) -> list[float]:
    s, known = c["shopper"], c["known"]
    overlap = sum(c["phrases"].get(f, 0) for f in p.phrases) - len(p.phrases) * c["counts"].get(p.id, 0)  # the product's own views left out
    return ranker.features(p, slot, req, c) + [
        sum(s.phrase_share.get(f, 0.0) for f in p.phrases) if known else NAN,
        min(overlap, 4),
        min(s.carted.get(p.id, 0), 3) if s else 0,
        math.log1p(c["co"].get(p.id, 0)),
        s.cart_rate if known else NAN,
        math.log1p(s.cat_carts.get(p.category, 0)) if known else NAN,
        s.brand_share.get(p.brand, 0.0) if known else NAN,
        s.sub_share.get(p.subcategory, 0.0) if known else NAN,
        p.id == c["first"],
        p.id in c["later"],
        p.category == c["main"],
        p.id in c["today"],
        p.subcategory in c["today_subs"]]


def candidates(state, c: dict) -> list:
    """The ranker's candidates plus carted products, co-viewed products and today's views."""
    s = c["shopper"]
    out = set(c["ids"]) | set(sorted(c["viewed"], key=c["viewed"].get, reverse=True)[:TOP]) | c["today"]
    if s:
        out.update(sorted(s.carted, key=s.carted.get, reverse=True)[:TOP])
    out.update(sorted(c["co"], key=c["co"].get, reverse=True)[:TOP])
    for v in c["views"]:
        out.update(state.by_subcategory[v.subcategory][:TOP])
    for ids in state.by_category.values():
        out.update(ids[:TOP // 2])
    for category in sorted(c["shares"], key=c["shares"].get, reverse=True)[:3]:
        out.update(state.by_category.get(category, ())[:TOP])
    return [state.products[pid] for pid in out if pid not in c["bought"] and state.available(pid)]


class Ranker2(Strategy):
    name = "ranker2"

    def __init__(self):
        self.models, self.mtimes = None, None

    def recommend(self, req, state):
        mtimes = tuple(m.stat().st_mtime if m.exists() else None for m in (MODEL, BUY_MODEL))
        if mtimes != self.mtimes:
            self.models = tuple(lgb.Booster(model_file=str(m)) for m in (MODEL, BUY_MODEL)) if all(mtimes) else None
            self.mtimes = mtimes
        if self.models is None:
            return rules4.STRATEGY.recommend(req, state)
        c = context(req, state)
        cands = candidates(state, c)
        if not cands:
            return []
        X = [features(p, 1, req, c) for p in cands]
        click, buy = (m.predict(X) for m in self.models)
        scored = sorted(((float(k) * float(b) * state.trend.get(p.subcategory, 1.0) * (2 - state.price_cut.get(p.id, 1.0)), p.id)
                         for k, b, p in zip(click, buy, cands)), reverse=True)
        return [pid for _, pid in scored[:10]]


STRATEGY = Ranker2()
