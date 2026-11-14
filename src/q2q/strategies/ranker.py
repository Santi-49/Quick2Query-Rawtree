"""Ranker: gradient-boosted trees trained on our own live feedback (q2q train), retrained as feedback grows.

Candidates come from the same places as in rules2. The model predicts the click on a candidate at slot 1;
the score is that click probability times the chance that a click becomes a purchase (81% for a recent
view, 27% otherwise, measured live), times trend and price cut. Bought products are never shown.
Until a model file exists it answers like rules2.
"""
import math

import lightgbm as lgb

from q2q import rt
from q2q.strategies import rules2
from q2q.strategy import Strategy

MODEL = rt.ROOT / "models" / "ranker.txt"
BUY_AFTER_CLICK = (0.27, 0.81)  # other product, recent view
PAGES, DEVICES = ["product", "category", "home"], ["android", "ios", "web"]
FEATURES = ["slot", "appeal", "log_views", "log_buys", "price", "is_new_product", "is_last_view", "in_views", "views_ago",
            "same_sub_last", "same_cat_last", "same_sub_any", "same_cat_any", "n_views", "viewed_before", "cat_share",
            "known_shopper", "segment", "page", "device", "new_shopper"]
TOP = 30


def context(req, state, live_purchases: bool = True) -> dict:
    """What is fixed for one request: the shopper, the session and the segment."""
    products = state.products
    views = [products[p] for p in req.views if p in products]
    shopper = state.shopper(req.user_id, live=live_purchases)
    return {"views": views, "ids": {v.id: len(views) - i for i, v in enumerate(views)},
            "subs": {v.subcategory for v in views}, "cats": {v.category for v in views},
            "bought": shopper.bought if shopper else (), "viewed": shopper.viewed if shopper else {},
            "shares": shopper.cat_share if shopper else {}, "segment": state.segment.get((req.device, req.region), {}),
            "page": PAGES.index(req.page) if req.page in PAGES else -1, "device": DEVICES.index(req.device) if req.device in DEVICES else -1}


def features(p, slot: int, req, c: dict) -> list[float]:
    last = c["views"][-1] if c["views"] else None
    return [slot, p.appeal, math.log1p(p.views), math.log1p(p.buys), p.price, p.is_new, bool(last and p.id == last.id), p.id in c["ids"],
            c["ids"].get(p.id, 0), bool(last and p.subcategory == last.subcategory), bool(last and p.category == last.category),
            p.subcategory in c["subs"], p.category in c["cats"], len(c["views"]), min(c["viewed"].get(p.id, 0), 20),
            c["shares"].get(p.category, 0.0), bool(c["shares"]), c["segment"].get(p.category, 1.0), c["page"], c["device"], req.is_new_user]


class Ranker(Strategy):
    name = "ranker"

    def __init__(self):
        self.model, self.mtime = None, None

    def recommend(self, req, state):
        mtime = MODEL.stat().st_mtime if MODEL.exists() else None
        if mtime != self.mtime:
            self.model, self.mtime = (lgb.Booster(model_file=str(MODEL)) if mtime else None), mtime
        if self.model is None:
            return rules2.STRATEGY.recommend(req, state)
        c = context(req, state)
        candidates = set(c["ids"]) | set(sorted(c["viewed"], key=c["viewed"].get, reverse=True)[:TOP])
        for v in c["views"]:
            candidates.update(state.by_subcategory[v.subcategory][:TOP])
        for ids in state.by_category.values():
            candidates.update(ids[:TOP // 2])
        for category in sorted(c["shares"], key=c["shares"].get, reverse=True)[:3]:
            candidates.update(state.by_category.get(category, ())[:TOP])
        candidates = [state.products[pid] for pid in candidates if pid not in c["bought"] and state.available(pid)]
        if not candidates:
            return []
        click = self.model.predict([features(p, 1, req, c) for p in candidates])
        scored = sorted(((float(k) * BUY_AFTER_CLICK[p.id in c["ids"]] * state.trend.get(p.subcategory, 1.0) * (2 - state.price_cut.get(p.id, 1.0)), p.id)
                         for k, p in zip(click, candidates)), reverse=True)
        return [pid for _, pid in scored[:10]]


STRATEGY = Ranker()
