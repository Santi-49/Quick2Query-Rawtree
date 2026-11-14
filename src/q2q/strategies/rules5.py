"""Rules 5: rules4 plus what the gap study found (docs/hypotheses/H-gap.md, our feedback 14 Nov 09:00-17:20 UTC,
78,354 requests, 791 purchases; rates are buys per slot-weighted impression).

Changes against rules4:
1. Today's organic carts (not bought) lead the list: 1.72% (returning) and 6.37% (new shoppers) against 0.69% / 1.24%
   for the first recent view; 47 buys; 40-44% of requests have one and we put it at slot 1 in 2% of them.
2. A one-view session's product beats the first of several views (1.17% / 2.33% against 0.69% / 1.24%, 56 vs 55 buys);
   the last of 2+ views is below a same-subcategory product (0.10% / 0.33% against 0.29% / 0.54%, 9 buys).
3. The product's own buys per view counts about one power more than appeal gives it: within class and route,
   buys ~ bpv^1.4-2.0 (Poisson fit, 750 buys); appeal carries bpv^0.5.
4. History carts by count: 0.64 / 0.82 / 1.50% for 1 / 2 / 3+ carts (171 buys); and by history views of the carted
   product: 0.93 / 0.57 / 0.41% for 1 / 2-3 / 4+ views.
5. No price-cut boost: cut products sold 11 against 19 expected at their class, route and category rates, clicks equal.
6. Home requests (no recent views): cold2, with one change. Among carted products, purchase grows with history buys
   as buys^0.36 (all pages, 171 buys) to ^0.54 (home, 22 buys), not buys^1 as cold2's best-seller base gives it, so a
   carted product's base is (buys + 5)^0.5 scaled to the top seller: carts lead the list (73% of returning home buys,
   0.50% per request with a cart at slot 1 against 0.19% for a top-category product), ordered by cart count
   (2+ carts x4.7 on home) more than by popularity. New shoppers keep the steep best-seller base (rank 1 0.30%,
   ranks 2-3 0.18%, others <= 0.11% per weighted impression).
"""
import math

from q2q.strategies import cold2
from q2q.strategies.cold2 import STRATEGY as COLD2
from q2q.strategies.rules4 import (BOTH, CARTED, CATEGORY_MAIN, CATEGORY_OTHER, FIRST_VIEW, OTHER_VIEW, SHARE_SESSION,
                                   SUBCATEGORY, TOP, VIEWED_BEFORE, VIEWED_ONLY, main_category)
from q2q.strategy import Strategy

TODAY_CART = 30.0       # carted today, not bought: x2.5 (returning) to x5 (new) the first view's rate
ONLY_VIEW = 18.0        # the single distinct recent view: x1.7-1.9 the first of several
LAST_VIEW = 3.0         # the last of 2+ distinct views: below a same-subcategory product (4.5)
CART_COUNT = (1.0, 1.3, 2.3)       # history carts 1 / 2 / 3+: 0.64 / 0.82 / 1.50%
CART_VIEWS = (1.0, 0.6, 0.45)      # history views of a carted product 1 / 2-3 / 4+: 0.93 / 0.57 / 0.41%
BPV_PRIOR, BPV_N, BPV_MID = 3.4, 20.0, 0.2  # shrunk buys per view, and its middle value (median 0.24)


def conversion(p) -> float:
    """The product's buys per view against the middle, shrunk; new products sit at the middle."""
    return ((p.buys + BPV_PRIOR) / (p.views + BPV_N) if p.views else BPV_MID) / BPV_MID


def home(req, state) -> list[tuple[float, str, dict]]:
    """cold2's list with carted products on a flatter popularity base (change 6)."""
    rows = COLD2.explain(req, state)
    shopper = state.shopper(req.user_id)
    carted = (getattr(shopper, "carted", None) or {}) if shopper else {}
    if not carted:
        return rows
    products, shares = state.products, shopper.cat_share
    top = products[state.best[0]].buys + 5 if state.best else 1
    rank = {c: i for i, c in enumerate(sorted(shares, key=shares.get, reverse=True))}
    today = state.today_views(req.user_id) if hasattr(state, "today_views") else []
    today_subs = {products[p].subcategory for p in today if p in products}
    segment = state.segment.get((req.device, req.region), {})
    damp = 0.5 if shares else 1.0
    merged = {pid: (s, pid, parts) for s, pid, parts in rows if pid not in carted}
    for pid, n in carted.items():  # every carted product, scored as cold2 does but on the flatter base
        p = products.get(pid)
        if p is None or pid in shopper.bought or not state.available(pid):
            continue
        r = rank.get(p.category)
        parts = {"best seller": (p.buys + 5) ** 0.5 * top ** 0.5 if not p.is_new else 5 + 20 * p.appeal,
                 "category rank": (cold2.RANK[r] if r < len(cold2.RANK) else cold2.OTHER) if r is not None else cold2.NEVER if shares else 1.0,
                 "cart": cold2.CART * (cold2.CART_TWICE if n >= 2 else 1.0),
                 "viewed before": 1.0,
                 "today": cold2.TODAY_PRODUCT if pid in today else cold2.TODAY_SUB if p.subcategory in today_subs else 1.0,
                 "segment": 1 + damp * (segment.get(p.category, 1.0) - 1),
                 "trend": state.trend.get(p.subcategory, 1.0)}
        merged[pid] = (math.prod(parts.values()), pid, parts)
    return sorted(merged.values(), key=lambda s: (s[0], s[1]), reverse=True)[:10]


class Rules5(Strategy):
    name = "rules5"

    def explain(self, req, state) -> list[tuple[float, str, dict]]:
        products = state.products
        views = [products[p] for p in req.views if p in products]
        if not views:
            return home(req, state)
        shopper = state.shopper(req.user_id)
        bought = shopper.bought if shopper else ()
        viewed = shopper.viewed if shopper else {}
        shares = shopper.cat_share if shopper else {}
        carted = getattr(shopper, "carted", None)  # history + today carts, not bought; None on an older State
        today = getattr(state, "_today_carts", {}).get(req.user_id, {})  # today's organic carts; see H-gap "state"
        segment = state.segment.get((req.device, req.region), {})
        damp = 0.5 if shares else 1.0

        main = main_category(views)
        single = len({v.id for v in views}) == 1
        relation: dict[str, float] = {}
        for i, v in enumerate(reversed(views)):
            last, first = i == 0, i == len(views) - 1
            own = ONLY_VIEW if single else FIRST_VIEW if first else LAST_VIEW if last else OTHER_VIEW
            for key, value in ((v.id, own), (v.subcategory, SUBCATEGORY[not last]),
                               (v.category, CATEGORY_MAIN if v.category == main else CATEGORY_OTHER)):
                relation[key] = max(relation.get(key, 0.0), value)

        candidates = {v.id for v in views} | set(today)
        candidates.update(sorted(viewed, key=viewed.get, reverse=True)[:2 * TOP])
        if carted:
            candidates.update(sorted(carted, key=carted.get, reverse=True)[:2 * TOP])
        for v in views:
            candidates.update(state.by_subcategory[v.subcategory][:2 * TOP])
        for ids in state.by_category.values():
            candidates.update(ids[:TOP])
        for category in sorted(shares, key=shares.get, reverse=True)[:3]:
            candidates.update(state.by_category.get(category, ())[:2 * TOP])

        scored = []
        for pid in candidates:
            if pid in bought or pid not in products or not state.available(pid):
                continue
            p = products[pid]
            session = relation.get(pid) or relation.get(p.subcategory) or relation.get(p.category) or 1.0
            if pid in today:
                before = TODAY_CART
            elif carted is None:
                before = VIEWED_BEFORE if pid in viewed else 1.0
            elif pid in carted:
                n, seen = carted[pid] - today.get(pid, 0), viewed.get(pid, 1)
                before = CARTED * CART_COUNT[min(n, 3) - 1] * CART_VIEWS[0 if seen <= 1 else 1 if seen <= 3 else 2]
            else:
                before = VIEWED_ONLY
            parts = {"appeal": p.appeal,
                     "conversion": conversion(p),
                     "session": max(session, before) if before > 1 else session,
                     "viewed before": (BOTH if session > 1 else 1.0) if before > 1 else 1.0,
                     "favourite category": 1 + SHARE_SESSION * shares.get(p.category, 0.0),
                     "segment": 1 + damp * (segment.get(p.category, 1.0) - 1),
                     "trend": state.trend.get(p.subcategory, 1.0)}
            scored.append((math.prod(parts.values()), pid, parts))
        scored.sort(key=lambda s: (s[0], s[1]), reverse=True)
        return scored[:10]

    def recommend(self, req, state):
        return [pid for _, pid, _ in self.explain(req, state)]


STRATEGY = Rules5()
