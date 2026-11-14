"""Stratified random exploration: pick one stratum, sample up to 10 of its products uniformly.

req.log carries the stratum and the propensity, so the answers can be evaluated off-policy.
"""
import random

from q2q.strategy import N, Strategy

BASE = {"recent": 0.15, "subcategory": 0.20, "category": 0.20, "favourites": 0.20, "new": 0.10, "anything": 0.15}


class Explore(Strategy):
    name = "explore"

    def __init__(self):
        self.rng = random.Random()

    def recommend(self, req, state):
        known = [p for p in req.views if p in state.products]
        last = state.products[known[-1]] if known else None
        shopper = state.shopper(req.user_id)
        favourites = [p for p, n in shopper.viewed.items() if n >= 2] if shopper else []
        if shopper and not favourites and shopper.cat_share:  # no repeat views: their largest category
            favourites = state.by_category.get(max(shopper.cat_share, key=shopper.cat_share.get), [])
        pools = {
            "recent": list(dict.fromkeys(known)),
            "subcategory": state.by_subcategory.get(last.subcategory, []) if last else [],
            "category": state.by_category.get(last.category, []) if last else [],
            "favourites": favourites,
            "new": state.new_products,
            "anything": list(state.products),
        }
        pools = {k: [p for p in v if state.available(p)] for k, v in pools.items()}
        names = [k for k in BASE if pools[k]]
        if not names:
            req.log = {"stratum": "none", "p_stratum": 1.0, "pool": 0, "propensity": 1.0, "n": 0}
            return []
        name = self.rng.choices(names, weights=[BASE[k] for k in names])[0]
        p_stratum = BASE[name] / sum(BASE[k] for k in names)
        pool = pools[name]
        items = self.rng.sample(pool, min(N, len(pool)))
        req.log = {"stratum": name, "p_stratum": p_stratum, "pool": len(pool),
                   "propensity": p_stratum * min(1, N / len(pool)), "n": len(items)}
        return items


STRATEGY = Explore()
