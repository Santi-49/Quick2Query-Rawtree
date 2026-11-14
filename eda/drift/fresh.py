"""H-drift tests 4 and 5: ranker2 trained on different slices of the past, replayed on the same later window.

    uv run python eda/drift/fresh.py 18:45 21:45 [--cached]    # scoring window, UTC today
    uv run python eda/drift/fresh.py 15:45 18:45 --cached

Variants, all fitted on train2's feature table (built once from all feedback, cached in data/drift/table.npz):
  all          every row before the window start (= training cut 0)
  cut20/60/180 every row before start - 20 / 60 / 180 minutes (test 5: freshness)
  last1h/2h/4h only the rows of the last 1 / 2 / 4 hours before start (test 4b)
  hl1h/2h/6h   every row before start, weight 0.5 ** (age / half-life) (test 4c)
  seed2/3      `all` with another LightGBM seed: the refit-to-refit noise any other difference must exceed
Models go to data/drift/models/<window>/<variant>/, never models/. Each variant is replayed as ranker2 through
q2q.replay (same requests, State rebuilt per request) and compared with `all`: paired differences of hit1, hit3,
hit10 per route, bootstrap se. state.trend is emptied: the replay State would otherwise apply the trend of now.
"""
import importlib.util
import sys

import lightgbm as lgb
import numpy as np
import pandas as pd

from q2q import replay, rt, train2
from q2q.state import State, epoch
from q2q.strategies import ranker2
from q2q.train import PARAMS

OUT = rt.ROOT / "data" / "drift"
FAST = {**PARAMS, "num_threads": 8}
VARIANTS = {"all": (0, None, None), "cut20": (20, None, None), "cut60": (60, None, None), "cut180": (180, None, None),
            "last1h": (0, 60, None), "last2h": (0, 120, None), "last4h": (0, 240, None),
            "hl1h": (0, None, 60), "hl2h": (0, None, 120), "hl6h": (0, None, 360),
            "seed2": (0, None, None), "seed3": (0, None, None)}  # cut minutes, window minutes, half-life minutes; seedN = all, other seed


def table(state, cached: bool):
    path = OUT / "table.npz"
    if cached and path.exists():
        z = np.load(path)
        return z["X"], z["y"], z["b"], z["t"]
    X, y, b, t, _ = train2.table(state)
    OUT.mkdir(parents=True, exist_ok=True)
    np.savez(path, X=X.astype(np.float32), y=y.astype(np.int8), b=b.astype(np.int8), t=t)
    return X, y, b, t


def frames(start: str, end: str, cached: bool) -> dict:
    paths = {k: OUT / f"{k}_{start[11:16].replace(':', '')}_{end[11:16].replace(':', '')}.parquet" for k in ("reqs", "buys", "today", "meta")}
    if cached and all(p.exists() for p in paths.values()):
        return {k: pd.read_parquet(p) for k, p in paths.items()}
    spec = importlib.util.spec_from_file_location("replay_pull", rt.ROOT / "eda" / "replay" / "pull.py")
    pull = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pull)
    buys = pd.concat([pull.run("events", start, end).assign(organic=True), pull.run("fed", start, end).assign(organic=False)], ignore_index=True)
    out = {"reqs": pull.run("reqs", start, end).sort_values("t", ignore_index=True), "buys": buys.sort_values("t", ignore_index=True),
           "today": pull.run("today", start, end).sort_values("t", ignore_index=True), "meta": pd.DataFrame([{"start": start, "end": end}])}
    for k, df in out.items():
        df.to_parquet(paths[k])
    return out


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    cached = "--cached" in sys.argv
    start, end = (f"2026-11-14 {a}:00" for a in args[:2])
    cut = epoch(start) * 1000
    state = State()
    state.load()
    X, y, b, t = table(state, cached)
    print(f"table {len(y):,} rows, {int(y.sum()):,} clicks, {int(b.sum()):,} purchases; window {start} to {end} UTC", flush=True)

    tag = start[11:16].replace(":", "") + "_" + end[11:16].replace(":", "")
    for name, (cut_min, win_min, hl_min) in VARIANTS.items():
        d = OUT / "models" / tag / name
        if cached and (d / "ranker2_buy.txt").exists():
            continue
        hi = cut - cut_min * 60_000
        keep = (t < hi) & ((t >= cut - win_min * 60_000) if win_min else True)
        w = 0.5 ** ((cut - t[keep]) / (hl_min * 60_000)) if hl_min else None
        k = y[keep] == 1
        params = {**FAST, "seed": int(name[4:])} if name.startswith("seed") else FAST
        click = lgb.train(params, lgb.Dataset(X[keep], y[keep], weight=w, feature_name=ranker2.FEATURES), num_boost_round=300)
        if name.startswith("seed"):
            p = {**(train2.SMALL if k.sum() < 1500 else PARAMS), "seed": int(name[4:])}
            buy = lgb.train(p, lgb.Dataset(X[keep][k], b[keep][k], feature_name=ranker2.FEATURES), num_boost_round=100 if k.sum() < 1500 else 300)
        else:
            buy = train2.fit_buy(X[keep][k], b[keep][k], None if w is None else w[k])
        d.mkdir(parents=True, exist_ok=True)
        click.save_model(str(d / "ranker2.txt"))
        buy.save_model(str(d / "ranker2_buy.txt"))
        ess = keep.sum() if w is None else w.sum() ** 2 / (w ** 2).sum()
        print(f"  {name:<7} {int(keep.sum()):>9,} rows (effective {ess:,.0f}), {int(k.sum()):,} clicks, {int(b[keep].sum())} purchases", flush=True)

    fr = frames(start, end, cached)
    reqs, shares, buys, today = replay.prepare(fr, 2500, 1000)
    print(f"replaying {len(reqs):,} requests ({(reqs['purchased'] != '').sum()} with a purchase); routes "
          + ", ".join(f"{r} {100 * shares.get(r, 0):.0f}%" for r in replay.ROUTES), flush=True)
    state._until = {}  # stock ignored, as replay.run
    state.trend = {}
    ind = {}
    for name in VARIANTS:
        d = OUT / "models" / tag / name
        if cached and (d / "indicators.parquet").exists():
            ind[name] = pd.read_parquet(d / "indicators.parquet")
            continue
        ranker2.MODEL, ranker2.BUY_MODEL = d / "ranker2.txt", d / "ranker2_buy.txt"
        ranker2.STRATEGY.mtimes = None
        tops = replay.replay(["ranker2"], reqs, state, buys, today)["ranker2"]
        ind[name] = replay.indicators(name, reqs, tops)
        ind[name].to_parquet(d / "indicators.parquet")

    rng = np.random.default_rng(0)
    print("\nlevels, % (n): " + " | ".join(f"{route} " + " ".join(f"{m} {100 * ind['all'].loc[ind['all']['route'] == route, m].mean():.1f}"
                                                                  for m in ("hit1", "hit3", "hit10")) for route in ("main", "new_shopper")))
    print("paired variant - all, points, same requests (± bootstrap se); n requests with a purchase per route: "
          + ", ".join(f"{r} {int(((reqs['route'] == r) & (reqs['purchased'] != '')).sum())}" for r in replay.ROUTES))
    cols = [(r, m) for r in ("main", "new_shopper", "no_views") for m in ("hit1", "hit3", "hit10")] + [("all", "hit3"), ("no_views", "organic10")]
    print(f"{'variant':<8}" + "".join(f"{r[:6] + ' ' + m:>17}" for r, m in cols))
    for name in VARIANTS:
        if name == "all":
            continue
        cells = []
        for route, m in cols:
            sel = ind["all"][m].notna().to_numpy() & ((reqs["route"] == route).to_numpy() if route != "all" else True)
            dlt = (ind[name][m] - ind["all"][m]).to_numpy()[sel]
            if not len(dlt):
                cells.append(f"{'-':>17}")
                continue
            if route == "all":  # routes weighted by share of requests
                rts = reqs["route"].to_numpy()[sel]
                wts = np.array([shares.get(r, 0) / (rts == r).sum() for r in rts])
                wts = wts / wts.sum()
                idx = rng.integers(0, len(dlt), (1000, len(dlt)))
                boot = (dlt[idx] * wts[idx]).sum(1) / wts[idx].sum(1)
                mean = float((dlt * wts).sum())
            else:
                boot = dlt[rng.integers(0, len(dlt), (1000, len(dlt)))].mean(1)
                mean = float(dlt.mean())
            cells.append(f"{100 * mean:+6.1f} ± {100 * boot.std():3.1f}".rjust(17))
        print(f"{name:<8}" + "".join(cells))


if __name__ == "__main__":
    main()
