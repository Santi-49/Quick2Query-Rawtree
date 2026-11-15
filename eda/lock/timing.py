"""Shadow timing of lock1 (and ranker2 for reference) on the 200 newest logged requests. Writes nothing.

    uv run python eda/lock/timing.py
"""
import time

import numpy as np

from q2q import rt
from q2q.state import State
from q2q.strategies import lock1, ranker2
from q2q.strategy import Request, guard

SQL = """SELECT request_id::String AS rid, toUnixTimestamp64Milli(ts::DateTime64(3, 'UTC')) AS t, user_id::String AS u, is_new_user::Bool AS new,
       context.page::String AS page, context.device::String AS device, context.region::String AS region,
       arrayMap(v -> v.product_id::String, recent_views::Array(JSON)) AS views
FROM shop.requests WHERE ts::DateTime64(3) > (SELECT max(ts::DateTime64(3)) FROM shop.requests) - INTERVAL 10 MINUTE
ORDER BY ts::DateTime64(3) DESC LIMIT 200"""

state = State()
state.load()
reqs = [Request(r["rid"], r["t"] / 1000, r["u"], bool(r["new"]), r["page"], r["device"], r["region"], list(r["views"])) for r in rt.query(SQL)]
for s in (lock1.STRATEGY, ranker2.STRATEGY):
    s.recommend(reqs[0], state)  # load the model
    ms, bad = [], 0
    for req in reqs:
        start = time.perf_counter()
        out = guard(s.recommend(req, state), state)
        ms.append(1000 * (time.perf_counter() - start))
        bad += len(out) != 10 or len(set(out)) != 10
    print(f"{s.name}: {len(reqs)} requests, median {np.median(ms):.1f} ms, p95 {np.percentile(ms, 95):.1f} ms, max {max(ms):.1f} ms, invalid lists {bad}")
    incat = [sum(state.products[p].category == state.products[r.views[-1]].category for p in s.recommend(r, state))
             for r in reqs if r.views and r.views[-1] in state.products]
    print(f"  slots in the last view's category: {np.mean(incat):.1f} of 10")
