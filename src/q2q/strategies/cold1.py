"""Cold 1: for requests with no recent views (the home page). docs/hypotheses/H-home-personal.md.

Base is how often a product was bought, as in the best-seller list, because on home requests of new
shoppers the best sellers beat our appeal order live. A returning shopper's own history then decides:
the favourite category as a power law of its share, and products viewed before and not bought.
A new shopper only has the segment of their device and region.
"""
import math

from q2q.strategy import Strategy

SHARE_POWER, SHARE_FLOOR = 1.5, 0.2  # (share / 10%) ^ 1.5: history x28 at a 60% share, live clicks agree in shape
VIEWED_BEFORE = 4.0                  # viewed and not bought: x7 overall, x3-4 inside the same category
TOP = 30


class Cold1(Strategy):
    name = "cold1"

    def explain(self, req, state) -> list[tuple[float, str, dict]]:
        products = state.products
        shopper = state.shopper(req.user_id)
        bought = shopper.bought if shopper else ()
        viewed = shopper.viewed if shopper else {}
        shares = shopper.cat_share if shopper else {}
        segment = state.segment.get((req.device, req.region), {})
        damp = 0.5 if shares else 1.0

        candidates = set(state.best[:2 * TOP]) | set(viewed)
        for category in sorted(shares, key=shares.get, reverse=True)[:3]:
            candidates.update(state.by_category.get(category, ())[:TOP])
        for category in sorted(segment, key=segment.get, reverse=True)[:3]:
            candidates.update(state.by_category.get(category, ())[:TOP])

        scored = []
        for pid in candidates:
            if pid in bought or not state.available(pid):
                continue
            p = products[pid]
            parts = {"best seller": p.buys + 5 if not p.is_new else 5 + 20 * p.appeal,
                     "favourite category": max(SHARE_FLOOR, (shares.get(p.category, 0.0) / 0.1) ** SHARE_POWER) if shares else 1.0,
                     "viewed before": VIEWED_BEFORE if pid in viewed else 1.0,
                     "segment": 1 + damp * (segment.get(p.category, 1.0) - 1),
                     "trend": state.trend.get(p.subcategory, 1.0)}
            scored.append((math.prod(parts.values()), pid, parts))
        scored.sort(key=lambda s: (s[0], s[1]), reverse=True)
        return scored[:10]

    def recommend(self, req, state):
        return [pid for _, pid, _ in self.explain(req, state)]


STRATEGY = Cold1()
