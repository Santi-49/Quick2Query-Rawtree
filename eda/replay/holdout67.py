"""Leak-free replay of ranker6 (bagged models) and ranker7 (organic purchase model) against ranker2.

    uv run eda/replay/holdout67.py 3 [--refresh] [--no-train]

As holdout3: every model is fitted on data before the window's start (feedback rows filtered by request time,
organic events by SQL), into data/replay/models67/, never models/. ranker7 runs twice: alpha 1 (organic buy model
alone) and alpha 0.5 (geometric blend with ranker2's buy model). Also prints buy-given-click AUC on our own clicks:
ranker2's buy model fitted on the oldest 80% against the organic model, on the newest 20% (the organic model
never saw a click). Then paired differences candidate - ranker2 on the same requests (bootstrap se).
"""
import sys
import time

import lightgbm as lgb
import numpy as np
import pandas as pd

from q2q import replay, rt, train2, train6, train7
from q2q.state import State, epoch
from q2q.strategies import ranker2, ranker6, ranker7
from q2q.train import PARAMS, auc

DIR = rt.ROOT / "data" / "replay" / "models67"
NAMES = ["ranker2", "ranker6", "ranker7", "ranker7h"]
STRATS = {"ranker2": ranker2.Ranker2(), "ranker6": ranker6.Ranker6(), "ranker7": ranker7.Ranker7(1.0), "ranker7h": ranker7.Ranker7(0.5)}
LINES = (("main", "hit1"), ("main", "hit3"), ("main", "hit10"), ("main", "hit10_not_r2"), ("new_shopper", "hit1"), ("new_shopper", "hit3"),
         ("new_shopper", "hit10"), ("new_shopper", "hit10_not_r2"), ("no_views", "organic10"))


def paired(reqs, tops: dict, reps: int = 1000) -> None:
    rng = np.random.default_rng(0)
    ind = {n: replay.indicators(n, reqs, tops[n]) for n in NAMES}
    not_r2 = (reqs["logger"] != "ranker2").to_numpy()
    print("paired candidate - ranker2, points, same requests (± bootstrap se, n)")
    for name in NAMES[1:]:
        for route, metric in LINES:
            col = metric.replace("_not_r2", "")
            keep = (reqs["route"] == route).to_numpy() & ind[name][col].notna().to_numpy() & (not_r2 if metric.endswith("_not_r2") else True)
            d = (ind[name][col] - ind["ranker2"][col]).to_numpy()[keep]
            se = d[rng.integers(0, len(d), (reps, len(d)))].mean(1).std()
            print(f"  {name:<9} {route:<12} {metric:<13} {100 * d.mean():+5.1f} ± {100 * se:3.1f} ({len(d)})")


def fit_all(cut: str) -> None:
    state = State()
    state.load()
    cut_ms = epoch(cut) * 1000
    query = rt.query
    rt.query = lambda sql, timeout=30: [r for r in query(sql, timeout) if not ("t" in r and float(r["t"]) >= cut_ms)]
    start = time.time()
    X, y, b, t, g = train2.table(state)
    rt.query = query
    print(f"feedback table before the cut: {len(y):,} rows, {y.sum():,} clicks, {b.sum():,} purchases in {time.time() - start:.0f} s", flush=True)
    for path, model in ((ranker2.MODEL, lgb.train(PARAMS, lgb.Dataset(X, y, feature_name=ranker2.FEATURES), num_boost_round=300)),
                        (ranker2.BUY_MODEL, train2.fit_buy(X[y == 1], b[y == 1]))):
        model.save_model(str(path))
    print("ranker2 refitted", flush=True)
    train6.train(state, (X, y, b, t, g))
    organic = train7.train(state, cut)
    new = t > np.quantile(t, 0.8)
    k = new & (y == 1)
    buy80 = train2.fit_buy(X[~new & (y == 1)], b[~new & (y == 1)])
    b6 = train6.predict([lgb.Booster(model_file=str(f)) for f in ranker6.files()[1]], X[y == 1])  # in-sample, reference only
    print(f"buy | click AUC on our newest 20% of clicks ({k.sum()}, {b[k].sum()} purchases): ranker2 buy (oldest 80%) {auc(b[k], buy80.predict(X[k])):.3f}, "
          f"organic {auc(b[k], organic.predict(X[k])):.3f}, geometric blend {auc(b[k], np.sqrt(buy80.predict(X[k]) * organic.predict(X[k]))):.3f}; "
          f"organic on all {(y == 1).sum()} clicks {auc(b[y == 1], organic.predict(X[y == 1])):.3f}; ranker6 buy in-sample {auc(b[y == 1], b6):.3f}", flush=True)


def main(hours: float, refresh: bool, fit: bool) -> None:
    snap = {k: DIR / f"{k}_{hours:g}h.parquet" for k in ("reqs", "buys", "today", "meta")}  # own copy: the shared cache is refreshed by others
    if refresh or not all(p.exists() for p in snap.values()):
        frames = replay.pull(hours, refresh=refresh)
        DIR.mkdir(parents=True, exist_ok=True)
        for k, p in snap.items():
            frames[k].to_parquet(p)
    frames = {k: pd.read_parquet(p) for k, p in snap.items()}
    cut = frames["meta"].iloc[0]["start"]
    print(f"window {cut} to {frames['meta'].iloc[0]['end']} UTC; training on data before {cut}", flush=True)
    DIR.mkdir(parents=True, exist_ok=True)
    train2.MODEL = ranker2.MODEL = DIR / "ranker2.txt"
    train2.BUY_MODEL = ranker2.BUY_MODEL = DIR / "ranker2_buy.txt"
    ranker6.DIR = DIR
    ranker7.BUY_MODEL = DIR / "ranker7_buy.txt"
    if fit:
        fit_all(cut)
    reqs, shares, buys, today = replay.prepare(frames, 2500, 1000)
    state = State()
    state.load()
    state._until = {}  # stock ignored, as replay.run
    replay.load = STRATS.get
    tops = replay.replay(NAMES, reqs, state, buys, today)
    print(f"({len(reqs):,} requests replayed)")
    print("values in %, ± bootstrap se, (n requests)\n" + replay.table({n: replay.summarize(replay.indicators(n, reqs, tops[n]), shares) for n in NAMES}))
    paired(reqs, tops)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(float(args[0]) if args else 3, "--refresh" in sys.argv, "--no-train" not in sys.argv)
