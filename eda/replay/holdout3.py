"""Leak-free replay of ranker3 against ranker2 and rules5: both rankers trained on feedback before the window.

    uv run eda/replay/holdout3.py 3 [--refresh]     # window = last 3 hours
    uv run eda/replay/holdout3.py 3 --no-train      # reuse the holdout models already in data/replay/models/

As holdout.py, plus what ranker3 reads from the State that the replay does not rebuild: the time of each cart
today and our clicks earlier today (feedback, not bought), both as of each replayed request.
Models go to data/replay/models/, never models/. After the replay table, paired differences ranker3 - other on the
same requests (bootstrap se), with hit10 also on the requests logged by neither ranker2 nor rules5.
"""
import sys
from bisect import bisect_left

import numpy as np

from q2q import replay, rt, train2, train3
from q2q.state import State, epoch
from q2q.strategies import ranker2, ranker3

DIR = rt.ROOT / "data" / "replay" / "models"
CLICKS = """SELECT r.u AS u, f.p AS p, f.q AS q, f.t AS t FROM
    (SELECT request_id::String AS rid, any(clicked::String) AS p, any(purchased::String) AS q, any(toUnixTimestamp64Milli(ts::DateTime64(3, 'UTC')) / 1000) AS t
     FROM {TEAM}.feedback WHERE clicked::String != '' GROUP BY rid) f
    INNER JOIN (SELECT request_id::String AS rid, any(user_id::String) AS u FROM shop.requests GROUP BY rid) r ON r.rid = f.rid"""


NAMES = ["rules5", "ranker2", "ranker3"]


def paired(reqs, tops: dict, today: dict, reps: int = 1000) -> None:
    rng = np.random.default_rng(0)
    ind = {n: replay.indicators(n, reqs, tops[n]) for n in NAMES}
    common = ~reqs["logger"].isin(["ranker2", "rules5"]).to_numpy()
    print("paired ranker3 - other, points, same requests (± bootstrap se, n)")
    for other in ("ranker2", "rules5"):
        for route, metric in (("main", "hit1"), ("main", "hit3"), ("main", "hit10"), ("new_shopper", "hit1"), ("new_shopper", "hit3"),
                              ("new_shopper", "hit10"), ("main", "hit10_common"), ("new_shopper", "hit10_common"), ("no_views", "organic10")):
            col = "hit10" if metric == "hit10_common" else metric
            keep = (reqs["route"] == route).to_numpy() & ind["ranker3"][col].notna().to_numpy() & (common if metric == "hit10_common" else True)
            d = (ind["ranker3"][col] - ind[other][col]).to_numpy()[keep]
            se = d[rng.integers(0, len(d), (reps, len(d)))].mean(1).std()
            print(f"  vs {other:<8} {route:<12} {metric:<13} {100 * d.mean():+5.1f} ± {100 * se:3.1f} ({len(d)})")
    carted = []  # the purchased product was carted today before the request
    for u, t, q in zip(reqs["u"], reqs["t"], reqs["purchased"]):
        ts, ps, cs = today.get(u, ((), [], []))
        carted.append(bool(q) and q in {p for p, c in zip(ps[:bisect_left(ts, t)], cs) if c})
    carted = np.array(carted)
    print(f"purchases of a product carted today: {carted.sum()} of {(reqs['purchased'] != '').sum()}; hit1 / hit3 / hit10 on them: "
          + ", ".join(f"{n} " + " / ".join(f"{100 * ind[n][m].to_numpy()[carted].mean():.0f}" for m in ("hit1", "hit3", "hit10")) for n in NAMES))


def main(hours: float, refresh: bool, fit: bool = True) -> None:
    frames = replay.pull(hours, refresh=refresh)
    cut_ms = epoch(frames["meta"].iloc[0]["start"]) * 1000
    print(f"training on feedback before {frames['meta'].iloc[0]['start']} UTC", flush=True)
    DIR.mkdir(parents=True, exist_ok=True)
    train2.MODEL = ranker2.MODEL = DIR / "ranker2.txt"
    train2.BUY_MODEL = ranker2.BUY_MODEL = DIR / "ranker2_buy.txt"
    train3.MODEL = ranker3.MODEL = DIR / "ranker3.txt"
    train3.BUY_MODEL = ranker3.BUY_MODEL = DIR / "ranker3_buy.txt"
    if fit:
        state = State()
        state.load()
        query = rt.query
        rt.query = lambda sql, timeout=30: [r for r in query(sql, timeout) if not ("t" in r and float(r["t"]) >= cut_ms)]
        train2.train(state)
        train3.train(state)
        rt.query = query

    clicks = {}
    for r in sorted(rt.query(CLICKS, timeout=60), key=lambda r: float(r["t"])):
        ts, ps, qs = clicks.setdefault(r["u"], ([], [], []))
        ts.append(float(r["t"]))
        ps.append(r["p"])
        qs.append(r["q"])
    base = replay.as_of

    def as_of(state, u, t, buys, today):
        base(state, u, t, buys, today)
        if not hasattr(state, "our_clicks_today"):
            state.our_clicks_today, state._cart_last = {}, {}
            state.today_cart_last = lambda user: state._cart_last.get(user, {})
        ts, ps, carts = today.get(u, ((), [], []))
        k = bisect_left(ts, t)
        state._cart_last[u] = {p: tt for tt, p, c in zip(ts[:k], ps[:k], carts[:k]) if c}
        ts, ps, qs = clicks.get(u, ((), [], []))
        j = bisect_left(ts, t)
        state.our_clicks_today[u] = {p for p, q in zip(ps[:j], qs[:j]) if p != q}

    replay.as_of = as_of
    reqs, shares, buys, today = replay.prepare(frames, 2500, 1000)
    state = State()
    state.load()
    state._until = {}  # stock ignored, as replay.run
    tops = replay.replay(NAMES, reqs, state, buys, today)
    print("values in %, ± bootstrap se, (n requests)\n" + replay.table({n: replay.summarize(replay.indicators(n, reqs, tops[n]), shares) for n in NAMES}))
    paired(reqs, tops, today)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(float(args[0]) if args else 3, "--refresh" in sys.argv, "--no-train" not in sys.argv)
