"""Shadow check of lock2 on the 200 newest home requests (no recent views). Writes nothing.

    uv run python eda/lock/home.py
"""
import time

import numpy as np

from q2q import rt
from q2q.state import State
from q2q.strategies import aff1, ranker2
from q2q.strategy import Request, guard

SQL = """SELECT request_id::String AS rid, toUnixTimestamp64Milli(ts::DateTime64(3, 'UTC')) AS t, user_id::String AS u, is_new_user::Bool AS new,
       context.page::String AS page, context.device::String AS device, context.region::String AS region
FROM shop.requests WHERE ts::DateTime64(3) > (SELECT max(ts::DateTime64(3)) FROM shop.requests) - INTERVAL 10 MINUTE
  AND length(recent_views::Array(JSON)) = 0
ORDER BY ts::DateTime64(3) DESC LIMIT 200"""

state = State()
state.load()
reqs = [Request(r["rid"], r["t"] / 1000, r["u"], bool(r["new"]), r["page"], r["device"], r["region"], []) for r in rt.query(SQL)]
print(f"{len(reqs)} home requests, {sum(bool(state.today_views(r.user_id)) for r in reqs)} with views today")
for s in (aff1.STRATEGY, ranker2.STRATEGY):
    s.recommend(reqs[0], state)
    ms, bad, same = [], 0, []
    for req in reqs:
        start = time.perf_counter()
        out = guard(s.recommend(req, state), state)
        ms.append(1000 * (time.perf_counter() - start))
        bad += len(out) != 10 or len(set(out)) != 10
        today = state.today_views(req.user_id)
        if today and today[-1] in state.products:
            same.append(sum(state.products[p].category == state.products[today[-1]].category for p in out))
    print(f"{s.name}: median {np.median(ms):.1f} ms, p95 {np.percentile(ms, 95):.1f} ms, invalid {bad}, in today's last category {np.mean(same):.1f} of 10")
