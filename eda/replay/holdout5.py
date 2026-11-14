"""Leak-free replay of ranker5 against ranker2: both trained on feedback before the window, the embedding built from
events before it.

    uv run eda/replay/holdout5.py 3 [--refresh]     # window = last 3 hours
    uv run eda/replay/holdout5.py 3 --no-train      # reuse data/replay/models5/

Models and the embedding go to data/replay/models5/, never models/ or data/emb/. After the replay table, paired
differences ranker5 - ranker2 on the same requests (bootstrap se), hit1 / hit3 / hit10 also on requests ranker2 did not log (_notr2), and
the time per request of each strategy.
"""
import sys
import time

import numpy as np

from q2q import emb, replay, rt, train2, train5
from q2q.state import State, epoch
from q2q.strategies import ranker2, ranker5

DIR = rt.ROOT / "data" / "replay" / "models5"
NAMES = ["ranker2", "ranker5"]


def paired(reqs, tops: dict, reps: int = 1000) -> None:
    rng = np.random.default_rng(0)
    ind = {n: replay.indicators(n, reqs, tops[n]) for n in NAMES}
    other = (reqs["logger"] != "ranker2").to_numpy()
    print("paired ranker5 - ranker2, points, same requests (± bootstrap se, n)")
    for route in ("main", "new_shopper", "no_views"):
        for metric in ("hit1", "hit3", "hit10", "hit1_notr2", "hit3_notr2", "hit10_notr2", "organic10"):
            col = metric.removesuffix("_notr2")
            keep = (reqs["route"] == route).to_numpy() & ind["ranker5"][col].notna().to_numpy() & (other if metric.endswith("_notr2") else True)
            if keep.sum() < 20:
                continue
            d = (ind["ranker5"][col] - ind["ranker2"][col]).to_numpy()[keep]
            se = d[rng.integers(0, len(d), (reps, len(d)))].mean(1).std()
            print(f"  {route:<12} {metric:<12} {100 * d.mean():+5.1f} ± {100 * se:3.1f} ({len(d)})  "
                  f"[r2 {100 * ind['ranker2'][col].to_numpy()[keep].mean():.1f}, r5 {100 * ind['ranker5'][col].to_numpy()[keep].mean():.1f}]")
    same = np.mean([a[:10] == b[:10] for a, b in zip(tops["ranker2"], tops["ranker5"])])
    print(f"identical top 10 on {100 * same:.0f}% of requests")


def main(hours: float, refresh: bool, fit: bool = True) -> None:
    frames = replay.pull(hours, refresh=refresh)
    start = frames["meta"].iloc[0]["start"]
    cut_ms = epoch(start) * 1000
    print(f"training on feedback before {start} UTC", flush=True)
    DIR.mkdir(parents=True, exist_ok=True)
    train2.MODEL = ranker2.MODEL = DIR / "ranker2.txt"
    train2.BUY_MODEL = ranker2.BUY_MODEL = DIR / "ranker2_buy.txt"
    train5.MODEL = ranker5.MODEL = DIR / "ranker5.txt"
    train5.BUY_MODEL = ranker5.BUY_MODEL = DIR / "ranker5_buy.txt"
    ranker5.EMB, ranker5.IDS = DIR / "products.npy", DIR / "products.json"
    if fit:
        emb.build(str(start)[:19], DIR)
        state = State()
        state.load()
        query = rt.query
        rt.query = lambda sql, timeout=30: [r for r in query(sql, timeout) if not ("t" in r and float(r["t"]) >= cut_ms)]
        train2.train(state)
        train5.train(state)
        rt.query = query

    reqs, shares, buys, today = replay.prepare(frames, 2500, 1000)
    state = State()
    state.load()
    state._until = {}  # stock ignored, as replay.run
    r = reqs.iloc[0]  # a failing strategy would be hidden by replay's fallback: call it once directly
    ranker5.STRATEGY.recommend(replay.Request(r.rid, r.t, r.u, bool(r.new), r.page, r.dev, r.reg, list(r.vp)), state)
    assert ranker5.STRATEGY.models is not None and ranker5.embedding() is not None
    t = time.perf_counter()
    tops = replay.replay(NAMES, reqs, state, buys, today)
    print(f"{len(reqs)} requests in {time.perf_counter() - t:.0f} s")
    print("values in %, ± bootstrap se, (n requests)\n" + replay.table({n: replay.summarize(replay.indicators(n, reqs, tops[n]), shares) for n in NAMES}))
    paired(reqs, tops)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(float(args[0]) if args else 3, "--refresh" in sys.argv, "--no-train" not in sys.argv)
