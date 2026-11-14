"""Hot 1: cold2 for the home page, times what converts right now. docs/hypotheses/H-home-hot.md.

cold2's score (best sellers x category rank x carts x today x segment x trend), times three more parts:
  conv        the product's purchases per view in shop.events over the last WINDOW minutes, shrunk to the
              average (PRIOR pseudo-views), over the average, clipped to [1/CLIP, CLIP]
  bought sub  BOUGHT_SUB if the shopper bought in the product's subcategory before (history or today)
  sub share   1 + SUB_SHARE x the subcategory's share of the shopper's history views
Bought products are never shown (cold2's rule; the carousel never sells them, H-home-personal).

The live counts come from one aggregate query in a background thread, at most every EVERY seconds with a
timeout: never a query per request. Before the first load, or on any error, the answer is cold2's list.
Rejected offline (14 Nov): +1.2 points organic top 10 over cold2, all from the two history parts; below ranker2.
"""
import math
import threading
import time

from q2q import rt
from q2q.strategies import cold2
from q2q.strategies.cold2 import CART, CART_TWICE, NEVER, OTHER, RANK, TODAY_PRODUCT, TODAY_SUB, TOP, VIEWED_BEFORE
from q2q.strategy import Strategy

WINDOW = 120       # minutes of shop.events behind the conversion part
PRIOR = 20.0       # pseudo-views at the average purchase rate
CLIP = 3.0
BOUGHT_SUB = 3.0
SUB_SHARE = 5.0
EVERY = 300.0      # seconds between refreshes
TIMEOUT = 20.0
SQL = f"""WITH (SELECT max(ts::DateTime64(3)) FROM shop.events) AS now
SELECT product_id::String AS p, countIf(event_type::String = 'view') AS v, countIf(event_type::String = 'purchase') AS b
FROM shop.events WHERE ts::DateTime64(3) > now - INTERVAL {WINDOW} MINUTE GROUP BY p"""


def conv_from(rows: list[dict]) -> dict[str, float]:
    """product -> shrunk purchases per view over the average, clipped."""
    v, b = sum(int(r["v"]) for r in rows), sum(int(r["b"]) for r in rows)
    if not v or not b:
        return {}
    avg = b / v
    return {r["p"]: min(CLIP, max(1 / CLIP, (int(r["b"]) + PRIOR * avg) / (int(r["v"]) + PRIOR) / avg)) for r in rows}


class Hot1(Strategy):
    name = "hot1"

    def __init__(self, auto: bool = True):
        self.conv = None   # replaced in one assignment by the refresh thread
        self.auto = auto
        self._thread = None

    def _loop(self) -> None:
        while True:
            try:
                conv = conv_from(rt.query(SQL, timeout=TIMEOUT))
                if conv:
                    self.conv = conv
            except Exception as e:  # noqa: BLE001 - keep the previous counts
                print(f"hot1: refresh failed: {str(e)[:200]}")
            time.sleep(EVERY)

    def recommend(self, req, state):
        if self.auto and self._thread is None:
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()
        conv = self.conv
        if not conv:
            return cold2.STRATEGY.recommend(req, state)
        try:
            return self.rank(req, state, conv)
        except Exception as e:  # noqa: BLE001 - never worse than cold2
            print(f"hot1: {str(e)[:200]}")
            return cold2.STRATEGY.recommend(req, state)

    def rank(self, req, state, conv: dict[str, float]) -> list[str]:
        products = state.products
        shopper = state.shopper(req.user_id)
        bought = shopper.bought if shopper else set()
        viewed = shopper.viewed if shopper else {}
        shares = shopper.cat_share if shopper else {}
        carted = shopper.carted if shopper else {}
        sub_share = shopper.sub_share if shopper else {}
        today = state.today_views(req.user_id)
        today_subs = {products[p].subcategory for p in today if p in products}
        bought_subs = {products[p].subcategory for p in bought if p in products}
        rank = {c: i for i, c in enumerate(sorted(shares, key=shares.get, reverse=True))}
        segment = state.segment.get((req.device, req.region), {})
        damp = 0.5 if shares else 1.0

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
            score = math.prod((
                p.buys + 5 if not p.is_new else 5 + 20 * p.appeal,
                (RANK[r] if r < len(RANK) else OTHER) if r is not None else NEVER if shares else 1.0,
                CART * (CART_TWICE if carted[pid] >= 2 else 1.0) if pid in carted else 1.0,
                VIEWED_BEFORE if pid in viewed and pid not in carted else 1.0,
                TODAY_PRODUCT if pid in today else TODAY_SUB if p.subcategory in today_subs else 1.0,
                1 + damp * (segment.get(p.category, 1.0) - 1),
                state.trend.get(p.subcategory, 1.0),
                conv.get(pid, 1.0),
                BOUGHT_SUB if p.subcategory in bought_subs else 1.0,
                1 + SUB_SHARE * sub_share.get(p.subcategory, 0.0)))
            scored.append((score, pid))
        scored.sort(reverse=True)
        return [pid for _, pid in scored[:10]]


STRATEGY = Hot1()
