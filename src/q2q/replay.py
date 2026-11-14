"""Offline replay: score strategies on our logged requests of the last N hours. Not a simulator; only logged outcomes.

    uv run q2q replay rules4 ranker2 cold2 --hours 4 [--refresh] [--organic 4000] [--sample 2000]

Each strategy answers every replayed request through guard(), as the router does. Metrics per route (main,
new_shopper, no_views) and overall (routes weighted by their share of the window's requests), each with a
bootstrap standard error:

  hit@1/3/10   requests where a shown product was purchased: that product is in the strategy's top k
  hit@10 oth   the same on requests whose list came from another arm (fallback counts as baseline): hit@k favours
               the arm that produced the logged list, because only what it showed can be purchased
  organic@10   requests followed within 30 min by an organic purchase (shop.events) of a product we did not show:
               one of those products is in the top 10. Sees products we never showed; matters most for home
  overlap      share of the top 10 that was in the logged list (uniform sample of requests)

explore-IPS is not computed. The explore arm logs only the propensity of the stratum it drew, not the marginal
probability of a product over the overlapping strata (subcategory inside category inside anything), and a
deterministic top 10 almost never matches its random slots. It also had 2 purchases in 1,331 requests by 14 Nov
17:40 UTC, too few for any estimate.

State approximations. The catalogue, appeal, trend, price cuts, segments and co-views are as of now. Stock is
ignored: every active product counts as available. Live purchases, today's views and carts are rebuilt per
request from what happened before it. Models (ranker, ranker2) and hand-set weights were fitted on feedback
that includes the window, so their scores are partly in-sample.
"""
import importlib.util
import time
from bisect import bisect_left
from collections import Counter

import numpy as np
import pandas as pd

from q2q import rt
from q2q.serve import route_for
from q2q.strategy import Request, decode, guard, load

ROUTES = ["main", "new_shopper", "no_views"]
METRICS = ["hit1", "hit3", "hit10", "hit10_other", "organic10", "overlap"]
WINDOW = 1800.0      # organic purchase within 30 min of the request
TODAY_KEEP = 10      # as State


def pull(hours: float, refresh: bool) -> dict:
    spec = importlib.util.spec_from_file_location("replay_pull", rt.ROOT / "eda" / "replay" / "pull.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.pull(hours, refresh)


def by_user(df: pd.DataFrame, cols: list[str]) -> dict:
    """user -> (times sorted, column lists...)."""
    return {u: (g["t"].to_numpy(), *(g[c].tolist() for c in cols)) for u, g in df.groupby("u", sort=False)}


def prepare(frames: dict, n_organic: int, n_sample: int, seed: int = 0) -> tuple[pd.DataFrame, dict, dict, dict]:
    """The requests to replay (purchases, a sample of organic ones, a uniform sample), route shares, buys and today by user."""
    reqs, buys = frames["reqs"].copy(), frames["buys"]
    reqs["route"] = ["no_views" if len(v) == 0 else "new_shopper" if n else "main" for v, n in zip(reqs["vp"], reqs["new"])]
    reqs["logger"] = ["baseline" if s == "fallback" else decode(m) if m else "baseline" for s, m in zip(reqs["served"], reqs["mv"])]
    shares = (reqs["route"].value_counts() / len(reqs)).to_dict()
    organic = by_user(buys[buys["organic"]], ["p"])
    last_event = buys.loc[buys["organic"], "t"].max()
    org = []
    for u, t, shown in zip(reqs["u"], reqs["t"], reqs["shown"]):
        ts, ps = organic.get(u, (np.array([]), []))
        lo, hi = np.searchsorted(ts, t, "right"), np.searchsorted(ts, t + WINDOW, "right")
        org.append(sorted(set(ps[lo:hi]) - set(shown)) if t + WINDOW <= last_event else [])
    reqs["organic"] = org
    rng = np.random.default_rng(seed)
    has_org = np.flatnonzero(reqs["organic"].str.len() > 0)
    keep_org = set(rng.choice(has_org, min(n_organic, len(has_org)), replace=False).tolist())
    reqs["organic"] = [o if i in keep_org else [] for i, o in enumerate(org)]
    reqs["sample"] = False
    reqs.loc[rng.choice(len(reqs), min(n_sample, len(reqs)), replace=False), "sample"] = True
    keep = (reqs["purchased"] != "") | (reqs["organic"].str.len() > 0) | reqs["sample"]
    return reqs[keep].reset_index(drop=True), shares, by_user(buys, ["p"]), by_user(frames["today"], ["p", "cart"])


def as_of(state, u: str, t: float, buys: dict, today: dict) -> None:
    """Set the State's live purchases, today's views and carts of shopper u to what happened before t."""
    ts, ps = buys.get(u, ((), []))
    state._live[u] = set(ps[:bisect_left(ts, t)])
    ts, ps, carts = today.get(u, ((), [], []))
    views, cart_n = [], Counter()
    for p, c in zip(ps[:bisect_left(ts, t)], carts):
        if c:
            cart_n[p] += 1
        else:
            views = [x for x in views if x != p] + [p]
    state._today[u] = views[-TODAY_KEEP:]
    state._today_carts[u] = dict(cart_n)


def replay(names: list[str], reqs: pd.DataFrame, state, buys: dict, today: dict) -> dict[str, list[list[str]]]:
    """Top 10 per strategy per request, through guard() as the router; a failing call answers the guard's best sellers."""
    out = {n: [] for n in names}
    strategies = {n: load(n) for n in names}
    for r in reqs.itertuples(index=False):
        as_of(state, r.u, r.t, buys, today)
        for n, s in strategies.items():
            req = Request(r.rid, r.t, r.u, bool(r.new), r.page, r.dev, r.reg, list(r.vp))
            try:
                out[n].append(guard(s.recommend(req, state), state))
            except Exception:
                out[n].append(guard([], state))
    return out


def indicators(name: str, reqs: pd.DataFrame, tops: list[list[str]]) -> pd.DataFrame:
    """One row per request: route and each metric's value (NaN where it does not apply)."""
    rows = []
    for r, top in zip(reqs.itertuples(index=False), tops):
        top, nan = list(top), float("nan")
        bought = r.purchased if r.purchased else None
        hit = {k: float(bought in top[:k]) if bought else nan for k in (1, 3, 10)}
        rows.append({"route": r.route, "hit1": hit[1], "hit3": hit[3], "hit10": hit[10],
                     "hit10_other": hit[10] if r.logger != name else nan,
                     "organic10": float(bool(set(top) & set(r.organic))) if len(r.organic) else nan,
                     "overlap": len(set(top) & set(r.shown)) / 10 if r.sample else nan})
    return pd.DataFrame(rows)


def summarize(ind: pd.DataFrame, shares: dict, reps: int = 300, seed: int = 0) -> dict:
    """metric -> route (and 'all') -> (mean, bootstrap se, n). 'all' weights the routes by share."""
    rng = np.random.default_rng(seed)
    out = {}
    for m in METRICS:
        out[m], boots, weights, means = {}, [], [], []
        for route in ROUTES:
            v = ind.loc[ind["route"] == route, m].dropna().to_numpy()
            if not len(v):
                out[m][route] = (float("nan"), float("nan"), 0)
                continue
            b = v[rng.integers(0, len(v), (reps, len(v)))].mean(1)
            out[m][route] = (v.mean(), b.std(), len(v))
            boots.append(b)
            means.append(v.mean())
            weights.append(shares.get(route, 0.0))
        w = np.array(weights) / sum(weights) if weights and sum(weights) else None
        out[m]["all"] = (float(np.dot(w, means)), float(np.dot(w, boots).std()), int(ind[m].notna().sum())) if w is not None \
            else (float("nan"), float("nan"), 0)
    return out


def table(results: dict[str, dict]) -> str:
    head = f"{'strategy':>9} {'route':>11} " + " ".join(f"{m:>16}" for m in METRICS)
    lines = [head]
    for name, res in results.items():
        for route in ["all"] + ROUTES:
            cells = []
            for m in METRICS:
                mean, se, n = res[m][route]
                cells.append(f"{100 * mean:6.1f}±{100 * se:4.1f} ({n:>4})" if n else f"{'-':>16}")
            lines.append(f"{name:>9} {route:>11} " + " ".join(f"{c:>16}" for c in cells))
    return "\n".join(lines)


def run(names: list[str], hours: float = 4, refresh: bool = False, n_organic: int = 4000, n_sample: int = 2000) -> dict:
    from q2q.state import State

    start = time.time()
    frames = pull(hours, refresh)
    meta = frames["meta"].iloc[0]
    reqs, shares, buys, today = prepare(frames, n_organic, n_sample)
    print(f"window {meta['start']} to {meta['end']} UTC: {len(frames['reqs']):,} requests, shares "
          + ", ".join(f"{r} {100 * shares.get(r, 0):.0f}%" for r in ROUTES)
          + f"; replaying {len(reqs):,} ({(reqs['purchased'] != '').sum()} with a purchase, "
          f"{(reqs['organic'].str.len() > 0).sum()} with an organic purchase, {reqs['sample'].sum()} sampled)", flush=True)
    state = State()
    state.load()
    state._until = {}  # stock ignored: logged lists were valid when shown
    t = time.time()
    tops = replay(names, reqs, state, buys, today)
    print(f"replayed {len(names)} strategies in {time.time() - t:.0f} s", flush=True)
    results = {n: summarize(indicators(n, reqs, tops[n]), shares) for n in names}
    print("values in %, ± bootstrap se, (n requests)\n" + table(results))
    print(f"total {time.time() - start:.0f} s")
    return results
