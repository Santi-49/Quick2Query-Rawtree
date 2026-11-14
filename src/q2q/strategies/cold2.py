"""Cold 2: for requests with no recent views (the home page). docs/hypotheses/H-home-ceiling.md.

Live feedback on home requests (14 Nov, 9,400 returning and 3,900 new-shopper requests, rates per slot-weighted
impression) says what cold1 got wrong. A product the shopper viewed and did not cart is barely better than one
never seen (0.035% against 0.017%), so cold1's x4 on every viewed product spends slots on noise. The signal
behind "viewed before" is the cart: carted and not bought converts at 0.23% (carted once) and 0.92% (twice
or more): 16 of the 24 home purchases of returning shoppers. The favourite category works by rank, not
by share: live clicks 0.90 / 0.17 / 0.11% for the top / 2nd-3rd / other categories. New shoppers click
the all-time best sellers (every purchase they made on home was a top-14 product), lifted by their segment.

Carts and today's views are not in State yet (docs/hypotheses/cold2-state.md). Until they are, the two
multipliers that use them stay at 1 and the list is: best sellers x category rank x segment x trend.
"""
import math

from q2q.strategy import Strategy

RANK = (1.0, 0.3, 0.3)   # top category, 2nd, 3rd: live clicks x1 / x0.19 / x0.12, history buys x1 / x0.30 / x0.15
OTHER, NEVER = 0.1, 0.03  # 4th+ category (history x0.06, live clicks x0.12); a category never viewed (history x0.02)
VIEWED_BEFORE = 1.5       # viewed, never carted: live home x1.7 (4 buys), inside the top category no gain
CART, CART_TWICE = 20.0, 3.0  # carted not bought: x14 (once) to x54 (twice or more) over a shown product never touched, live home; set so carts lead the list
TODAY_PRODUCT = 4.0       # viewed earlier today: new shoppers x7.6 (2 buys, 6 clicks), returning clicks x3
TODAY_SUB = 3.0           # subcategory viewed earlier today: new shoppers x3.4 (7 buys), clicks x2.4 for returning
TOP = 30


class Cold2(Strategy):
    name = "cold2"

    def explain(self, req, state) -> list[tuple[float, str, dict]]:
        products = state.products
        shopper = state.shopper(req.user_id)
        bought = shopper.bought if shopper else ()
        viewed = shopper.viewed if shopper else {}
        shares = shopper.cat_share if shopper else {}
        carted = getattr(shopper, "carted", None) or {}           # product -> cart count, not in State yet
        today = getattr(state, "today_views", lambda u: [])(req.user_id)  # products viewed today, not in State yet
        today_subs = {products[p].subcategory for p in today if p in products}
        rank = {c: i for i, c in enumerate(sorted(shares, key=shares.get, reverse=True))}
        segment = state.segment.get((req.device, req.region), {})
        damp = 0.5 if shares else 1.0  # returning shoppers follow their segment half as much

        candidates = set(state.best[:2 * TOP]) | set(carted) | set(today)
        candidates.update(sorted(viewed, key=viewed.get, reverse=True)[:TOP])
        for category in list(rank)[:3]:
            candidates.update(state.by_category.get(category, ())[:TOP])
        for category in sorted(segment, key=segment.get, reverse=True)[:3]:
            candidates.update(state.by_category.get(category, ())[:TOP])
        for sub in today_subs:
            candidates.update(state.by_subcategory.get(sub, ())[:TOP])

        scored = []
        for pid in candidates:
            if pid in bought or pid not in products or not state.available(pid):
                continue
            p = products[pid]
            r = rank.get(p.category)
            parts = {"best seller": p.buys + 5 if not p.is_new else 5 + 20 * p.appeal,
                     "category rank": (RANK[r] if r < len(RANK) else OTHER) if r is not None else NEVER if shares else 1.0,
                     "cart": CART * (CART_TWICE if carted[pid] >= 2 else 1.0) if pid in carted else 1.0,
                     "viewed before": VIEWED_BEFORE if pid in viewed and pid not in carted else 1.0,
                     "today": TODAY_PRODUCT if pid in today else TODAY_SUB if p.subcategory in today_subs else 1.0,
                     "segment": 1 + damp * (segment.get(p.category, 1.0) - 1),
                     "trend": state.trend.get(p.subcategory, 1.0)}
            scored.append((math.prod(parts.values()), pid, parts))
        scored.sort(key=lambda s: (s[0], s[1]), reverse=True)
        return scored[:10]

    def recommend(self, req, state):
        return [pid for _, pid, _ in self.explain(req, state)]


STRATEGY = Cold2()
