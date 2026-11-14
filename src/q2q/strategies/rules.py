"""Rules: score = appeal x relation to the shopper x segment x trend x price cut, 0 if bought.

Every multiplier comes from an effect size in docs/SIMULATOR.md and is a prior to re-estimate live.
Relations are relative to "another category, never seen" = 1.
"""
import math

from q2q.strategy import Strategy

LAST_VIEW = 35.0        # the product being looked at: 4.4% live against 0.13% for another category
RECENT_VIEW = 20.0      # any other recent view
SUBCATEGORY = (6.0, 5.0)  # same subcategory as the last view, as an earlier view
CATEGORY = (4.0, 3.0)     # same category as the last view, as an earlier view
VIEWED_BEFORE = ((10, 15.0), (3, 6.0), (2, 3.0), (1, 1.5))  # history views of a product not bought
SHARE_HOME, SHARE_SESSION = 10.0, 2.0  # weight of the shopper's category share without and with recent views
TOP = 15                # candidates taken from each list


def viewed_before(count: int) -> float:
    return next((m for least, m in VIEWED_BEFORE if count >= least), 1.0)


class Rules(Strategy):
    name = "rules"

    def explain(self, req, state) -> list[tuple[float, str, dict]]:
        """The 10 best (score, product, multipliers by name). The dashboard shows the multipliers."""
        products = state.products
        views = [products[p] for p in req.views if p in products]
        shopper = state.shopper(req.user_id)
        bought = shopper.bought if shopper else ()
        viewed = shopper.viewed if shopper else {}
        shares = shopper.cat_share if shopper else {}
        segment = state.segment.get((req.device, req.region), {})

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
            parts = {"appeal": p.appeal,
                     "session": relation.get(pid) or relation.get(p.subcategory) or relation.get(p.category) or 1.0,
                     "viewed before": viewed_before(viewed.get(pid, 0)),
                     "favourite category": 1 + share_weight * shares.get(p.category, 0.0),
                     "segment": segment.get(p.category, 1.0),
                     "trend": state.trend.get(p.subcategory, 1.0),
                     "price cut": 2 - state.price_cut.get(pid, 1.0)}
            scored.append((math.prod(parts.values()), pid, parts))
        scored.sort(key=lambda s: (s[0], s[1]), reverse=True)
        return scored[:10]

    def recommend(self, req, state):
        return [pid for _, pid, _ in self.explain(req, state)]


STRATEGY = Rules()
