"""Rules 2: the rules strategy with multipliers re-estimated on live feedback (docs/hypotheses/H-live-factors.md).

Changes against rules: recent views count 3 times less, the shopper's favourite category counts 10 times more,
a past view is a flat x3 that does not multiply with the session effect, and segment lifts are halved for
returning shoppers. Relations are relative to "another category, never seen" = 1.
"""
import math

from q2q.strategy import Strategy

LAST_VIEW = 12.0        # live purchases x11 (17 purchases); a clicked recent view is bought 81% of the time
RECENT_VIEW = 12.0      # live x11, the same as the last view
SUBCATEGORY = (4.5, 4.0)  # live: no bonus over the category
CATEGORY = (4.5, 3.5)     # same category as the last view, as an earlier view
VIEWED_BEFORE = 3.0     # any history view of a product not bought: live x3.1, flat in the count
BOTH = 1.4              # session and past view together: the larger one, times this
SHARE_HOME, SHARE_SESSION = 15.0, 20.0  # weight of the shopper's category share without and with recent views
TOP = 15                # candidates taken from each list


class Rules2(Strategy):
    name = "rules2"

    def explain(self, req, state) -> list[tuple[float, str, dict]]:
        """The 10 best (score, product, multipliers by name). The dashboard shows the multipliers."""
        products = state.products
        views = [products[p] for p in req.views if p in products]
        shopper = state.shopper(req.user_id)
        bought = shopper.bought if shopper else ()
        viewed = shopper.viewed if shopper else {}
        shares = shopper.cat_share if shopper else {}
        segment = state.segment.get((req.device, req.region), {})
        damp = 0.5 if shopper and shopper.cat_share else 1.0  # returning shoppers follow their segment half as much

        relation: dict[str, float] = {}  # by product, subcategory or category of the session
        for i, v in enumerate(reversed(views)):
            first = i == 0
            for key, value in ((v.id, LAST_VIEW if first else RECENT_VIEW), (v.subcategory, SUBCATEGORY[not first]), (v.category, CATEGORY[not first])):
                relation[key] = max(relation.get(key, 0.0), value)

        candidates = {v.id for v in views}
        candidates.update(sorted(viewed, key=viewed.get, reverse=True)[:2 * TOP])
        for v in views:
            candidates.update(state.by_subcategory[v.subcategory][:2 * TOP])
        for ids in state.by_category.values():
            candidates.update(ids[:TOP])
        for category in sorted(shares, key=shares.get, reverse=True)[:3]:
            candidates.update(state.by_category.get(category, ())[:2 * TOP])

        share_weight = SHARE_SESSION if views else SHARE_HOME
        scored = []
        for pid in candidates:
            if pid in bought or not state.available(pid):
                continue
            p = products[pid]
            session = relation.get(pid) or relation.get(p.subcategory) or relation.get(p.category) or 1.0
            before = VIEWED_BEFORE if pid in viewed else 1.0
            parts = {"appeal": p.appeal,
                     "session": max(session, before) if before > 1 else session,
                     "viewed before": (BOTH if session > 1 else 1.0) if before > 1 else 1.0,
                     "favourite category": 1 + share_weight * shares.get(p.category, 0.0),
                     "segment": 1 + damp * (segment.get(p.category, 1.0) - 1),
                     "trend": state.trend.get(p.subcategory, 1.0),
                     "price cut": 2 - state.price_cut.get(pid, 1.0)}
            scored.append((math.prod(parts.values()), pid, parts))
        scored.sort(key=lambda s: (s[0], s[1]), reverse=True)
        return scored[:10]

    def recommend(self, req, state):
        return [pid for _, pid, _ in self.explain(req, state)]


STRATEGY = Rules2()
