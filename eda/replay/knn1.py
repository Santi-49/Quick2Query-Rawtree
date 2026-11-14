"""Offline test of session neighbours (knn1) against ranker2 and blend1. docs/hypotheses/H-sql-neighbours.md.

    uv run eda/replay/knn1.py [--refetch] [--rereplay]

Requests with recent views of the cached 3 h holdout window (data/replay/*_3h.parquet, as holdout3), two sets:
  shown    a shown product was purchased (hit = that product in the top k). Biased towards the arm that logged the
           list (ranker2 or rules5): only what was shown can be bought, so a list that never ran scores low.
  organic  no purchase from our list, but an organic purchase (shop.events) of a product we did not show within 30 min
           (hit = one of those products in the top k). Sees products we never showed; a sample of 500.
1. For each request, one wide neighbour query as of the request's ts (14 h back, covers all of today): every cart or
   purchase of another shopper's session that viewed one of the request's views, with the views it matched and its
   age. Cached in data/replay/knn_rows_3h.pkl. The query variants are scored from these rows in Python.
2. ranker2 and blend1 replayed with the holdout models in data/replay/models/ (fitted before the window), cached.
3. Hit rates per set and route; paired differences against ranker2 (bootstrap se).
"""
import math
import pickle
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

from q2q import replay, rt
from q2q.strategies import knn1, ranker2
from q2q.strategy import guard

DIR = rt.ROOT / "data" / "replay"
ROWS = DIR / "knn_rows_3h.pkl"
TOPS = DIR / "knn_tops_3h.pkl"
HIST = DIR / "knn_hist7.pkl"
WIDE = """WITH s AS (SELECT session_id::String AS sid, groupUniqArray(product_id::String) AS vs, dateDiff('second', max(ts::DateTime64(3)), {NOW}) AS age
  FROM shop.events WHERE {WIN} AND event_type::String = 'view' AND product_id::String IN ({VIEWS}) AND user_id::String != '{USER}' GROUP BY sid)
SELECT e.product_id::String AS p, e.event_type::String = 'purchase' AS buy, s.vs AS vs, s.age AS age
FROM shop.events e INNER JOIN s ON e.session_id::String = s.sid
WHERE {EWIN} AND e.event_type::String IN ('purchase', 'add_to_cart')"""
PAIRS = """SELECT a, b, count() AS n FROM
  (SELECT session_id::String AS sid, product_id::String AS a FROM shop.history_events
   WHERE ts::DateTime64(3) >= now64(3) - INTERVAL 8 DAY AND event_type::String = 'view' AND product_id::String IN ({SET}) GROUP BY sid, a) v
  INNER JOIN (SELECT session_id::String AS sid, product_id::String AS b FROM shop.history_events
   WHERE ts::DateTime64(3) >= now64(3) - INTERVAL 8 DAY AND event_type::String IN ('purchase', 'add_to_cart')) c ON c.sid = v.sid
WHERE a != b GROUP BY a, b ORDER BY n DESC LIMIT 40 BY a"""
POP = """SELECT product_id::String AS p, toUInt32(toUnixTimestamp(ts::DateTime64(3)) / 600) AS b, count() AS n FROM shop.events
WHERE event_type::String IN ('purchase', 'add_to_cart') GROUP BY p, b"""


def wide(views, user, t) -> list[dict]:
    now = f"toDateTime64({t:.3f}, 3)"
    win = f"ts::DateTime64(3) >= {now} - INTERVAL 14 HOUR AND ts::DateTime64(3) < {now}"
    sql = WIDE.replace("{EWIN}", win.replace("ts::", "e.ts::")).replace("{WIN}", win).replace("{NOW}", now)
    return rt.query(sql.replace("{VIEWS}", ",".join(f"'{v}'" for v in views)).replace("{USER}", user), timeout=60)


def fetch(reqs) -> dict:
    rows = pickle.loads(ROWS.read_bytes()) if ROWS.exists() and "--refetch" not in sys.argv else {}
    todo = reqs[~reqs["rid"].isin(rows)]
    if len(todo):
        t = time.time()
        with ThreadPoolExecutor(3) as pool:
            rows.update(zip(todo["rid"], pool.map(lambda r: wide(list(r[0]), r[1], r[2]), zip(todo["vp"], todo["u"], todo["t"]))))
        ROWS.write_bytes(pickle.dumps(rows))
        print(f"fetched {len(todo)} neighbour sets in {time.time() - t:.0f} s", flush=True)
    return rows


def history(reqs) -> dict:
    """view product -> {carted or bought product: sessions} over the last 7 days of shop.history_events (before today)."""
    ids = sorted({p for v in reqs["vp"] for p in v})
    out = pickle.loads(HIST.read_bytes()) if HIST.exists() else {}
    if not set(ids) <= set(out.get("_ids", ())):
        out = {"_ids": ids}
        for r in rt.query(PAIRS.replace("{SET}", ",".join(f"'{p}'" for p in ids)), timeout=120):
            out.setdefault(r["a"], {})[r["b"]] = r["n"]
        HIST.write_bytes(pickle.dumps(out))
    return out


def popularity() -> dict:
    """product -> (10-minute buckets sorted, cumulative carts and buys), to count a product's carts in any window."""
    df = pd.DataFrame(rt.query(POP, timeout=60)).sort_values(["p", "b"])
    return {p: (g["b"].to_numpy(), g["n"].cumsum().to_numpy()) for p, g in df.groupby("p")}


def carts_in(pop, p, t, hours) -> float:
    b, c = pop.get(p, (np.array([0]), np.array([0])))
    hi, lo = np.searchsorted(b, t / 600, "right"), np.searchsorted(b, (t - hours * 3600) / 600, "right")
    return float((c[hi - 1] if hi else 0) - (c[lo - 1] if lo else 0))


def score(rows, views, hours=12.0, buy=1.0, decay=0.0, recent=0.0, keep_seen=False, alpha=0.0, pop=None, t=0.0) -> list[str]:
    """The neighbour list from the wide rows, as one query variant would rank it. alpha > 0 divides by the product's
    carts and buys in the window to the power alpha (lift instead of count)."""
    views = list(dict.fromkeys(reversed(views)))[::-1]
    n = len(views)
    wv = {v: 1 + recent * i / max(n - 1, 1) for i, v in enumerate(views)}
    seen, w = set(views), {}
    for r in rows:
        if r["age"] > hours * 3600 or (not keep_seen and r["p"] in seen):
            continue
        ov = sum(wv.get(v, 0.0) for v in r["vs"])
        w[r["p"]] = w.get(r["p"], 0.0) + ov * (buy if r["buy"] else 1.0) * math.exp(-decay * r["age"] / 3600)
    if alpha:
        w = {p: x / (carts_in(pop, p, t, hours) + 5) ** alpha for p, x in w.items()}
    return sorted(w, key=lambda p: (-w[p], p))[:20]


def hist_list(hist, views) -> list[str]:
    w = {}
    for v in set(views):
        for b, n in hist.get(v, {}).items():
            if b not in views:
                w[b] = w.get(b, 0) + n
    return sorted(w, key=lambda p: (-w[p], p))[:20]


def fuse(base: list[str], nb: list[str], weight: float) -> list[str]:
    s = {}
    for wt, lst in ((1.0, base), (weight, nb[:10])):
        for i, p in enumerate(lst):
            s[p] = s.get(p, 0.0) + wt / (knn1.K + i)
    return sorted(s, key=s.get, reverse=True)[:10]


def hits(reqs, tops) -> pd.DataFrame:
    """hit@k: the purchased product (shown set) or one of the organic purchases (organic set) in the top k."""
    targets = [{q} if q else set(o) for q, o in zip(reqs["purchased"], reqs["organic"])]
    return pd.DataFrame({f"hit{k}": [float(bool(g & set(top[:k]))) for g, top in zip(targets, tops)] for k in (1, 3, 10)})


def main():
    frames = replay.pull(3, refresh=False)
    _, _, buys, today = replay.prepare(frames, 0, 0)
    reqs, _, _, _ = replay.prepare(frames, 2500, 0)
    reqs = reqs[reqs["vp"].str.len() > 0].reset_index(drop=True)
    shown = reqs[reqs["purchased"] != ""]
    organic = reqs[(reqs["purchased"] == "") & (reqs["organic"].str.len() > 0)].sample(500, random_state=0)
    reqs = pd.concat([shown.assign(set="shown"), organic.assign(set="organic")], ignore_index=True)
    print(f"window {frames['meta'].iloc[0]['start']} to {frames['meta'].iloc[0]['end']} UTC: {len(shown)} shown purchases with views, "
          f"{len(organic)} organic ones sampled", flush=True)
    rows = fetch(reqs)
    hist = history(reqs)
    pop = popularity()

    from q2q.state import State
    ranker2.MODEL, ranker2.BUY_MODEL = DIR / "models" / "ranker2.txt", DIR / "models" / "ranker2_buy.txt"
    state = State()
    state.load()
    state._until = {}
    cached = pickle.loads(TOPS.read_bytes()) if TOPS.exists() and "--rereplay" not in sys.argv else {}
    todo = reqs[~reqs["rid"].isin(cached)].reset_index(drop=True)
    if len(todo):
        got = replay.replay(["ranker2", "blend1"], todo, state, buys, today)
        cached.update({rid: (a, b) for rid, a, b in zip(todo["rid"], got["ranker2"], got["blend1"])})
        TOPS.write_bytes(pickle.dumps(cached))
    tops = {"ranker2": [cached[r][0] for r in reqs["rid"]], "blend1": [cached[r][1] for r in reqs["rid"]]}

    me = {"hours": knn1.HOURS, "buy": knn1.BUY, "recent": knn1.RECENT, "keep_seen": knn1.KEEP_SEEN}
    variants = {"nb 12h": {}, "nb 3h": {"hours": 3}, "nb today": {"hours": 14}, "nb buy x2": {"buy": 2.0}, "nb buy x4": {"buy": 4.0},
                "nb decay 0.3/h": {"decay": 0.3}, "nb recent x2": {"recent": 1.0}, "nb recent x4": {"recent": 3.0},
                "nb keep seen": {"keep_seen": True}, "nb lift 0.5": {"alpha": 0.5}, "knn1 list": me}
    nbs = {name: [score(rows[r], list(v), pop=pop, t=t, **kw) for r, v, t in zip(reqs["rid"], reqs["vp"], reqs["t"])] for name, kw in variants.items()}
    nbs["hist7"] = [hist_list(hist, list(v)) for v in reqs["vp"]]
    nbs["knn1 list + hist7"] = [fuse(a, b, 0.5) for a, b in zip(nbs["knn1 list"], nbs["hist7"])]
    for name in ("nb 12h", "nb 3h"):
        print(f"coverage {name}: 5+ products {100 * np.mean([len(x) >= 5 for x in nbs[name]]):.0f}%, 10+ {100 * np.mean([len(x) >= 10 for x in nbs[name]]):.0f}%")
    res = {"ranker2": tops["ranker2"], "blend1": tops["blend1"]}
    res.update({name: [guard(x, state) for x in lst] for name, lst in nbs.items()})
    for wt in (0.15, 0.3, 0.6):
        res[f"knn1 w{wt}"] = [guard(fuse(b, x, wt), state) for b, x in zip(tops["ranker2"], nbs["knn1 list"])]
    for wt in (0.15, 0.3):
        res[f"excl-seen w{wt}"] = [guard(fuse(b, x, wt), state) for b, x in zip(tops["ranker2"], nbs["nb 12h"])]
    res["knn1+hist7 w0.3"] = [guard(fuse(b, x, 0.3), state) for b, x in zip(tops["ranker2"], nbs["knn1 list + hist7"])]
    print(f"knn1: hours {knn1.HOURS}, buy x{knn1.BUY}, recent x{1 + knn1.RECENT}, keep seen {knn1.KEEP_SEEN}, fusion weight {knn1.WEIGHT}")
    print("values in %, ± se; paired difference against ranker2 ± bootstrap se")
    rng = np.random.default_rng(0)
    for kind in ("shown", "organic"):
        sub = (reqs["set"] == kind).to_numpy()
        for route in ("main", "new_shopper"):
            keep = sub & (reqs["route"] == route).to_numpy()
            base = hits(reqs[keep], [t for t, k in zip(res["ranker2"], keep) if k])
            print(f"\n{kind}, {route} (n {keep.sum()})")
            print(f"{'':>18} {'top1':>11} {'top3':>11} {'top10':>11} {'d top1':>11} {'d top3':>11} {'d top10':>11}")
            for name, t in res.items():
                h = hits(reqs[keep], [x for x, k in zip(t, keep) if k])
                cells = [f"{100 * h[m].mean():4.1f}±{100 * h[m].std() / math.sqrt(len(h)):3.1f}" for m in ("hit1", "hit3", "hit10")]
                diffs = []
                for m in ("hit1", "hit3", "hit10"):
                    d = (h[m] - base[m]).to_numpy()
                    diffs.append(f"{100 * d.mean():+5.1f}±{100 * d[rng.integers(0, len(d), (500, len(d)))].mean(1).std():3.1f}")
                print(f"{name:>18} " + " ".join(f"{c:>11}" for c in cells + diffs))


if __name__ == "__main__":
    main()
