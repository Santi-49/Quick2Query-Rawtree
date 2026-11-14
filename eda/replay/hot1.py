"""Offline test of hot1 against cold2 and ranker2 on home requests (no recent views). docs/hypotheses/H-home-hot.md.

    uv run eda/replay/hot_pull.py      # once: home requests of today and live counts, data/replay/hot_*.parquet
    uv run eda/replay/hot1.py [--rereplay]

Requests: every home request of 09:30 to 22:32 UTC 14 Nov with a feedback row, two sets as knn1.py:
  shown    a shown product was purchased (hit = it is in the top k). Biased towards the arm that logged the list.
  organic  an organic purchase (shop.events) within 30 min of a product we did not show (hit = one in the top k).
State as of each request (replay.as_of: live purchases, today's views and carts). hot1's live counts as of the last
complete 10-minute bucket before the request, the last WINDOW minutes, through hot1.conv_from (the live code path).
cold2 and ranker2 (holdout models of data/replay/models, fitted before 18:28) replayed once and cached.
Variants: hot1 (all parts), "conv only" (BOUGHT_SUB 1, SUB_SHARE 0). Paired differences, bootstrap se, per window:
all day, before 18:28 (ranker2 in-sample) and from 18:28 (ranker2 out-of-sample).
"""
import math
import pickle
import sys
import time

import numpy as np
import pandas as pd

from q2q import replay, rt
from q2q.strategies import hot1, ranker2
from q2q.strategy import guard

DIR = rt.ROOT / "data" / "replay"
TOPS = DIR / "hot_tops.pkl"
SPLIT = pd.Timestamp("2026-11-14 18:28:32", tz="UTC").timestamp()


def conv_table(counts: pd.DataFrame):
    """bucket -> cumulative (views, purchases) per product, and a function t -> hot1.conv_from rows as of t."""
    c = counts[counts["d"] == ""]
    b0 = int(c["b"].min())
    pids = sorted(c["p"].unique())
    ix = {p: i for i, p in enumerate(pids)}
    nb = int(c["b"].max()) - b0 + 1
    cum = {}
    for e in ("view", "purchase"):
        a = np.zeros((len(pids), nb))
        s = c[c["e"] == e]
        np.add.at(a, (s["p"].map(ix).to_numpy(), (s["b"] - b0).to_numpy()), s["n"].to_numpy())
        cum[e] = np.cumsum(a, 1)
    memo = {}

    def at(t: float) -> dict:
        hi = int(t // 600) - b0 - 1
        if hi not in memo:
            lo = hi - hot1.WINDOW // 10
            w = {e: cum[e][:, hi] - (cum[e][:, lo] if lo >= 0 else 0) for e in cum}
            memo[hi] = hot1.conv_from([{"p": p, "v": w["view"][i], "b": w["purchase"][i]} for i, p in enumerate(pids)])
        return memo[hi]
    return at


def hits(targets, tops) -> np.ndarray:
    return np.array([[float(bool(g & set(t[:k]))) for k in (1, 3, 10)] for g, t in zip(targets, tops)])


def main():
    f = {k: pd.read_parquet(DIR / f"hot_{k}.parquet") for k in ("reqs", "buys", "today", "counts", "meta")}
    reqs, _, buys, today = replay.prepare(f, 10 ** 9, 0)
    print(f"window {f['meta'].iloc[0]['start']} to {f['meta'].iloc[0]['end']} UTC: {len(f['reqs']):,} home requests, "
          f"{(reqs['purchased'] != '').sum()} with a shown purchase, {(reqs['organic'].str.len() > 0).sum()} with an organic one", flush=True)
    from q2q.state import State
    ranker2.MODEL, ranker2.BUY_MODEL = DIR / "models" / "ranker2.txt", DIR / "models" / "ranker2_buy.txt"
    state = State()
    state.load()
    state._until = {}
    cached = pickle.loads(TOPS.read_bytes()) if TOPS.exists() and "--rereplay" not in sys.argv else {}
    todo = reqs[~reqs["rid"].isin(cached)].reset_index(drop=True)
    if len(todo):
        got = replay.replay(["cold2", "ranker2"], todo, state, buys, today)
        cached.update({rid: (a, b) for rid, a, b in zip(todo["rid"], got["cold2"], got["ranker2"])})
        TOPS.write_bytes(pickle.dumps(cached))
    res = {"cold2": [cached[r][0] for r in reqs["rid"]], "ranker2": [cached[r][1] for r in reqs["rid"]]}

    at = conv_table(f["counts"])
    s = hot1.Hot1(auto=False)
    variants = {"hot1": (hot1.BOUGHT_SUB, hot1.SUB_SHARE), "conv only": (1.0, 0.0)}
    took, unreachable = {}, []
    for name, (bs, ss) in variants.items():
        hot1.BOUGHT_SUB, hot1.SUB_SHARE = bs, ss
        out, t0 = [], 0.0
        for r in reqs.itertuples(index=False):
            replay.as_of(state, r.u, r.t, buys, today)
            req = replay.Request(r.rid, r.t, r.u, bool(r.new), r.page, r.dev, r.reg, list(r.vp))
            s.conv = at(r.t)
            t = time.perf_counter()
            out.append(guard(s.recommend(req, state), state))
            t0 += time.perf_counter() - t
            if name == "hot1":
                sh = state.shopper(r.u)
                unreachable.append(bool(r.organic) and set(r.organic) <= (sh.bought if sh else set()))
        res[name], took[name] = out, 1000 * t0 / len(reqs)
    hot1.BOUGHT_SUB, hot1.SUB_SHARE = variants["hot1"]
    print("ms per request: " + ", ".join(f"{n} {v:.1f}" for n, v in took.items()) + " (cold2 and ranker2: see 'seconds per strategy' on a --rereplay)")

    targets = [{q} if q else set(o) for q, o in zip(reqs["purchased"], reqs["organic"])]
    H = {n: hits(targets, t) for n, t in res.items()}
    shown = (reqs["purchased"] != "").to_numpy()
    new = reqs["new"].to_numpy().astype(bool)
    late = (reqs["t"] >= SPLIT).to_numpy()
    unreachable = np.array(unreachable)
    print(f"organic requests whose only targets were bought before (no list can show them): {unreachable.sum()} of {(~shown).sum()}")
    rng = np.random.default_rng(0)
    for wname, wmask in (("all day", np.ones(len(reqs), bool)), ("before 18:28", ~late), ("from 18:28", late)):
        print(f"\n== {wname}: hit rate % top 1/3/10; paired difference ± bootstrap se")
        for label, m in (("shown, returning", shown & ~new), ("shown, new", shown & new), ("shown, all", shown),
                         ("organic, returning", ~shown & ~new), ("organic, new", ~shown & new), ("organic, all", ~shown),
                         ("organic, reachable", ~shown & ~unreachable)):
            m = m & wmask
            print(f"  {label} (n {m.sum()}): " + ", ".join(f"{n} " + "/".join(f"{100 * x:.1f}" for x in H[n][m].mean(0)) for n in res))
            idx = rng.integers(0, m.sum(), (1000, m.sum()))
            for name in variants:
                for other in ("cold2", "ranker2"):
                    d = (H[name] - H[other])[m]
                    se = d[idx].mean(1).std(0)
                    print(f"      {name} - {other:<8} " + "  ".join(f"top{k} {100 * a:+5.1f} ± {100 * b:3.1f}" for k, a, b in zip((1, 3, 10), d.mean(0), se)))


if __name__ == "__main__":
    main()
