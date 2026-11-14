"""Shadow timing of ranker3 (and ranker2 for reference) on the 300 newest logged requests. Writes nothing.

    uv run python eda/replay/timing3.py
"""
import time

import numpy as np

from q2q import rt
from q2q.state import State
from q2q.strategies import ranker2, ranker3
from q2q.strategy import Request, guard

SQL = """SELECT request_id::String AS rid, toUnixTimestamp64Milli(ts::DateTime64(3, 'UTC')) AS t, user_id::String AS u, is_new_user::Bool AS new,
       context.page::String AS page, context.device::String AS device, context.region::String AS region,
       arrayMap(v -> v.product_id::String, recent_views::Array(JSON)) AS views
FROM shop.requests WHERE ts::DateTime64(3) > (SELECT max(ts::DateTime64(3)) FROM shop.requests) - INTERVAL 10 MINUTE
ORDER BY ts::DateTime64(3) DESC LIMIT 300"""

state = State()
state.load()
reqs = [Request(r["rid"], r["t"] / 1000, r["u"], bool(r["new"]), r["page"], r["device"], r["region"], list(r["views"])) for r in rt.query(SQL)]
for s in (ranker3.STRATEGY, ranker2.STRATEGY):
    s.recommend(reqs[0], state)  # load the model
    ms, bad, cart1, has = [], 0, 0, 0
    for req in reqs:
        start = time.perf_counter()
        out = guard(s.recommend(req, state), state)
        ms.append(1000 * (time.perf_counter() - start))
        bad += len(out) != 10 or len(set(out)) != 10 or not all(state.available(p) for p in out)
        carts = set(state.today_carts(req.user_id))
        has += bool(carts)
        cart1 += bool(out and out[0] in carts)
    print(f"{s.name}: {len(reqs)} requests, median {np.median(ms):.1f} ms, p95 {np.percentile(ms, 95):.1f} ms, max {max(ms):.1f} ms, "
          f"invalid lists {bad}; slot 1 is a today cart on {cart1} of {has} requests with one", flush=True)
