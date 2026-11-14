"""Leak-free test of ranker8 against ranker2 and blend1 on the window not used to choose ranker8 (19:00 UTC to END).

    uv run eda/replay/test8.py [--no-train]

Needs data/replay/abl/table.npz (ablation8.py table). ranker2 (its 34 columns, train2's parameters) and ranker8
(train8.fit) are fitted on every row before 19:00, no subsampling, into data/replay/abl/test/, never models/.
blend1 uses that ranker2. Replay: requests with a purchase, State as of each request as prod has it (no cart times,
no own clicks). Then paired differences ranker8 - other (bootstrap se), per route and on purchases of products carted today.
"""
import importlib.util
import sys

import lightgbm as lgb
import numpy as np

from q2q import replay, rt, train2, train8
from q2q.state import epoch
from q2q.strategies import blend1, ranker2, ranker8, rules5
from q2q.train import PARAMS

spec = importlib.util.spec_from_file_location("ablation8", rt.ROOT / "eda" / "replay" / "ablation8.py")
abl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(abl)

DIR = abl.DIR / "test"
START, END = "2026-11-14 19:00:00", "2026-11-14 22:00:00"
N2 = len(ranker2.FEATURES)
NAMES = ["ranker2", "blend1", "rules5", "ranker8"]


def fit() -> None:
    d = np.load(abl.DIR / "table.npz")
    old = d["t"] < epoch(START) * 1000
    X, y, b = d["X"][old], d["y"][old], d["b"][old]
    print(f"rows before {START}: {len(y):,}, clicks {y.sum():,}, purchases {b.sum()}", flush=True)
    lgb.train(PARAMS, lgb.Dataset(X[:, :N2], y, feature_name=ranker2.FEATURES), num_boost_round=300).save_model(str(ranker2.MODEL))
    train2.fit_buy(X[y == 1][:, :N2], b[y == 1]).save_model(str(ranker2.BUY_MODEL))
    for path, model in zip((ranker8.MODEL, ranker8.BUY_MODEL), train8.fit(X[:, ranker8.COLS], y, b)):
        model.save_model(str(path))
    print("fitted ranker2 and ranker8", flush=True)


def main(train: bool) -> None:
    DIR.mkdir(parents=True, exist_ok=True)
    ranker2.MODEL, ranker2.BUY_MODEL = DIR / "ranker2.txt", DIR / "ranker2_buy.txt"
    ranker8.MODEL, ranker8.BUY_MODEL = DIR / "ranker8.txt", DIR / "ranker8_buy.txt"
    if train:
        fit()
    frames = abl.pull_window(START, END)
    reqs, buys, today = abl.purchases(frames)
    state = abl.State()
    state.load()
    state._until = {}
    replay.load = {"ranker2": ranker2.STRATEGY, "blend1": blend1.STRATEGY, "rules5": rules5.STRATEGY, "ranker8": ranker8.STRATEGY}.get
    tops = replay.replay(NAMES, reqs, state, buys, today)
    print(f"{len(reqs)} purchase requests, {START} to {END}; per-request ms = seconds above / {len(reqs)} x 1000")
    ind = {n: replay.indicators(n, reqs, tops[n]) for n in NAMES}
    tc = abl.carted_today(reqs, today)
    for n in NAMES:
        print(f"  {n:<8} " + " | ".join(f"{route} " + "/".join(f"{100 * ind[n].loc[ind[n]['route'] == route, m].mean():.1f}" for m in ("hit1", "hit3", "hit10"))
                                        for route in ("main", "new_shopper", "no_views"))
              + f" | carted today ({tc.sum()}) " + "/".join(f"{100 * ind[n][m].to_numpy()[tc].mean():.0f}" for m in ("hit1", "hit3", "hit10")))
    rng = np.random.default_rng(0)
    for other in ("ranker2", "blend1"):
        print(f"paired ranker8 - {other}, points ± bootstrap se (n)")
        not_logged = ~reqs["logger"].isin([other, "ranker2", "rules5", "blend1"]).to_numpy()
        for label, mask in (("main", (reqs["route"] == "main").to_numpy()), ("new_shopper", (reqs["route"] == "new_shopper").to_numpy()),
                            ("no_views", (reqs["route"] == "no_views").to_numpy()), ("all", np.ones(len(reqs), bool)), ("carted today", tc),
                            ("all, logged by none of the four", not_logged)):
            cells = []
            for m in ("hit1", "hit3", "hit10"):
                dd = (ind["ranker8"][m] - ind[other][m]).to_numpy()[mask]
                se = dd[rng.integers(0, len(dd), (1000, len(dd)))].mean(1).std()
                cells.append(f"{m} {100 * dd.mean():+5.1f} ± {100 * se:3.1f}")
            print(f"  {label:<32} " + ", ".join(cells) + f" ({mask.sum()})")


if __name__ == "__main__":
    main("--no-train" not in sys.argv)
