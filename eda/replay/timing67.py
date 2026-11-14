"""Shadow timing of ranker6 and ranker7 (and ranker2 for reference) on the 300 newest logged requests. Writes nothing.

    uv run python eda/replay/timing67.py
"""
import time

import numpy as np

from q2q import rt
from q2q.state import State
from q2q.strategies import ranker2, ranker6, ranker7
from q2q.strategy import Request, guard

SQL = """SELECT request_id::String AS rid, toUnixTimestamp64Milli(ts::DateTime64(3, 'UTC')) AS t, user_id::String AS u, is_new_user::Bool AS new,
       context.page::String AS page, context.device::String AS device, context.region::String AS region,
       arrayMap(v -> v.product_id::String, recent_views::Array(JSON)) AS views
FROM shop.requests WHERE ts::DateTime64(3) > (SELECT max(ts::DateTime64(3)) FROM shop.requests) - INTERVAL 10 MINUTE
ORDER BY ts::DateTime64(3) DESC LIMIT 300"""

state = State()
state.load()
reqs = [Request(r["rid"], r["t"] / 1000, r["u"], bool(r["new"]), r["page"], r["device"], r["region"], list(r["views"])) for r in rt.query(SQL)]
print(f"ranker6 files: {[f.name for fs in ranker6.files() for f in fs]}")
for s in (ranker2.Ranker2(), ranker6.Ranker6(), ranker7.Ranker7(1.0), ranker7.Ranker7(0.5)):
    s.recommend(reqs[0], state)  # load the models
    ms, bad = [], 0
    for req in reqs:
        start = time.perf_counter()
        out = guard(s.recommend(req, state), state)
        ms.append(1000 * (time.perf_counter() - start))
        bad += len(out) != 10 or len(set(out)) != 10 or not all(state.available(p) for p in out)
    print(f"{s.name} {getattr(s, 'alpha', '')}: {len(reqs)} requests, median {np.median(ms):.1f} ms, p95 {np.percentile(ms, 95):.1f} ms, "
          f"max {max(ms):.1f} ms, invalid lists {bad}", flush=True)
