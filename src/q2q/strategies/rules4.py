"""Rules 4: rules2 with the session read from all recent views, not only the last one.

Changes against rules2 (live feedback to 16:18 UTC 14 Nov, every strategy pooled; history as support):
1. The first (oldest) recent view leads, not the last. Among re-shown recent views of the same popularity, the
   first converts x2.4 in clicks (2.29 vs 0.94 per 100 weighted impressions, 74 vs 37 clicks; history x1.95 on
   2,517 vs 1,592 clicks). Later views, the last one included, convert like a same-subcategory product
   (rules2 lists: buys 0.39 vs 0.85 per 100 weighted impressions) yet rules2 put them in slots 1-3 62% of the
   time. FIRST_VIEW 12 (as rules2), OTHER_VIEW 5 (history ratio of 2 gives 6, live gives 3-4.5).
   docs/hypotheses/H-reshow-rank.md, H-slot-order.md, H-session-shape.md
2. The session's main category is the one with the most views (ties: the earliest view), not the last view's.
   When they differ (9% of requests), the majority category gets x1.6 clicks and x2.8 buys over the last view's
   (35 vs 29 clicks); history: the carousel converted 0.81% when it showed a last-view category that was not the
   majority, 1.09% when it was. CATEGORY_MAIN 4.5, CATEGORY_OTHER 3.0. docs/hypotheses/H-category-page.md
3. A past cart, not a past view, carries the shopper's history (when the State has Shopper.carted). On best-seller
   lists (not chosen per shopper), non-home pages, against never-seen products: carted-not-bought outside the
   session category x5.6 clicks (24 vs 168 clicks), x6.1 buys; inside it x1.8 clicks (15). Viewed-not-carted
   x1.0 outside (16 clicks) and x0.5 inside (8). All lists pooled agree: carted x5.1 / x2.7 clicks (109 / 176),
   viewed-only x1.0 / x0.6 (69 / 117). CARTED 6 (with BOTH 1.4 in the session: x1.9), VIEWED_ONLY 1.
   Without carts on the State it falls back to rules2's VIEWED_BEFORE 3. sql/hypotheses/H-session-shape.sql, item 7.

Unchanged on purpose: no view-age term (flat in live and history, H-view-age), no repeat-view bonus (3.7% of
requests, 7 clicks), no price-direction term, and the same rule on product and category pages: the two pages
convert alike under rules2 once the session has views (2.02% vs 1.85%).
"""
import math

from q2q.strategy import Strategy

FIRST_VIEW = 12.0       # the oldest recent view, or the only one
OTHER_VIEW = 5.0        # any later recent view, the last one included
SUBCATEGORY = (4.5, 4.0)  # same subcategory as the last view, as an earlier view (as rules2)
CATEGORY_MAIN = 4.5     # the category holding most recent views, ties to the earliest view
CATEGORY_OTHER = 3.0    # any other category of a recent view
VIEWED_BEFORE = 3.0     # any history view of a product not bought: live x3.1, flat in the count (when carts are unknown)
CARTED = 6.0            # put in the cart in history, never bought: best-seller lists x5.6 clicks, x6.1 buys outside the session
VIEWED_ONLY = 1.0       # viewed in history, never carted: best-seller lists x1.0 clicks outside the session, x0.5 inside
BOTH = 1.4              # session and past view together: the larger one, times this
SHARE_HOME, SHARE_SESSION = 15.0, 20.0  # weight of the shopper's category share without and with recent views
TOP = 15                # candidates taken from each list


def main_category(views) -> str | None:
    """Category with the most views; a tie goes to the category viewed first."""
    cats = [v.category for v in views]
    return max(cats, key=lambda c: (cats.count(c), -cats.index(c))) if cats else None


class Rules4(Strategy):
    name = "rules4"

    def explain(self, req, state) -> list[tuple[float, str, dict]]:
        """The 10 best (score, product, multipliers by name). The dashboard shows the multipliers."""
        products = state.products
        views = [products[p] for p in req.views if p in products]
        shopper = state.shopper(req.user_id)
        bought = shopper.bought if shopper else ()
        viewed = shopper.viewed if shopper else {}
        shares = shopper.cat_share if shopper else {}
        carted = getattr(shopper, "carted", None)  # product -> history cart count, products not bought; None on an older State
        segment = state.segment.get((req.device, req.region), {})
        damp = 0.5 if shopper and shopper.cat_share else 1.0  # returning shoppers follow their segment half as much

        main = main_category(views)
        relation: dict[str, float] = {}  # by product, subcategory or category of the session
        for i, v in enumerate(reversed(views)):
            last, first = i == 0, i == len(views) - 1
            for key, value in ((v.id, FIRST_VIEW if first else OTHER_VIEW), (v.subcategory, SUBCATEGORY[not last]),
                               (v.category, CATEGORY_MAIN if v.category == main else CATEGORY_OTHER)):
                relation[key] = max(relation.get(key, 0.0), value)

        candidates = {v.id for v in views}
        candidates.update(sorted(viewed, key=viewed.get, reverse=True)[:2 * TOP])
        if carted:
            candidates.update(sorted(carted, key=carted.get, reverse=True)[:2 * TOP])
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
            if carted is None:
                before = VIEWED_BEFORE if pid in viewed else 1.0
            else:
                before = CARTED if pid in carted else VIEWED_ONLY
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


STRATEGY = Rules4()
