"""Train ranker8: train3's rows with every input of ranker8.ALL (ranker3's plus rules5's rank of the shown product, as
of the request), fitted on ranker8.FEATURES with PARAMS8.

    uv run python -m q2q.train8          # once, writes models/ranker8.txt and models/ranker8_buy.txt
    uv run python -m q2q.train8 1800     # again every 1800 s

rules5's rank needs the State as of each request: its live purchases, today's views and carts are set from what
happened before the request (as in replay), then restored. Validation as train3: oldest 80% fitted, newest 20% scored.
"""
import bisect
import sys
import time
from collections import Counter

import lightgbm as lgb
import numpy as np

from q2q.strategies import ranker3
from q2q.strategies.ranker8 import BUY_MODEL, COLS, FEATURES, MODEL, full_row, rules5_ranks
from q2q.strategy import Request
from q2q.train import PARAMS, auc
from q2q.train2 import ROWS2, TODAY, TODAY_KEEP, pulled, ranked
from q2q.train3 import BUYS, CARTS, by_user

PARAMS8 = {**PARAMS, "num_leaves": 7, "min_data_in_leaf": 400, "lambda_l2": 30.0, "feature_fraction": 0.7, "bagging_fraction": 0.8, "bagging_freq": 1}
BUY8 = {**PARAMS8, "min_data_in_leaf": 50}
ROUNDS, BUY_ROUNDS = 300, 150


def table(state):
    """X (all of ALL), click, buy, request time and request index per impression."""
    rows = sorted(pulled(ROWS2), key=lambda r: r["t"])
    today, carts, buys = by_user(pulled(TODAY)), by_user(pulled(CARTS)), by_user(pulled(BUYS))
    fed = {}
    for r in rows:
        if r["clicked"]:
            fed.setdefault(r["user_id"], []).append((r["t"], r["clicked"], r["purchased"]))
    saved = (state._live, state._today, state._today_carts, state._until)
    state._live, state._today, state._today_carts, state._until = dict(state._live), dict(state._today), dict(state._today_carts), {}
    X, y, b, t, g = [], [], [], [], []
    try:
        for i, r in enumerate(rows):
            now, u = int(r["t"]), r["user_id"]
            req = Request(r["rid"], now / 1000, u, bool(r["new"]), r["page"], r["device"], r["region"], list(r["views"]))
            ts, ps = today.get(u, ([], []))
            bts, bps = buys.get(u, ([], []))
            earlier = [(p, q) for tt, p, q in fed.get(u, ()) if tt < now]
            bought = set(bps[:bisect.bisect_left(bts, now)]) | {q for _, q in earlier if q}
            cts, cps = carts.get(u, ([], []))
            k = bisect.bisect_left(cts, now)
            cart_n = dict(Counter(cps[:k]))
            seen = ps[:bisect.bisect_left(ts, now)][-TODAY_KEEP:]
            c = ranker3.context(req, state, live=False, today=seen, carts=cart_n, cart_last={p: tt / 1000 for tt, p in zip(cts[:k], cps[:k])},
                                our={p for p, q in earlier if p != q}, bought_today=bought)
            state._live[u], state._today[u], state._today_carts[u] = bought, seen, cart_n
            r5 = rules5_ranks(req, state)
            for slot, pid in enumerate(r["shown"], 1):
                p = state.products.get(pid)
                if p is not None and pid not in c["bought"]:
                    X.append(full_row(p, req, c, r5, slot))
                    y.append(pid == r["clicked"])
                    b.append(pid == r["clicked"] and pid == r["purchased"])
                    t.append(now)
                    g.append(i)
    finally:
        state._live, state._today, state._today_carts, state._until = saved
    return np.array(X, dtype=float), np.array(y, dtype=int), np.array(b, dtype=int), np.array(t), np.array(g)


def fit(X, y, b, w=None):
    """Click and purchase-given-click models on the columns of X as given (FEATURES order when X = X_all[:, COLS])."""
    click = lgb.train(PARAMS8, lgb.Dataset(X, y, weight=w, feature_name=FEATURES), num_boost_round=ROUNDS)
    return click, lgb.train(BUY8, lgb.Dataset(X[y == 1], b[y == 1], feature_name=FEATURES), num_boost_round=BUY_ROUNDS)


def train(state) -> None:
    start = time.time()
    X, y, b, t, g = table(state)
    X = X[:, COLS]
    print(f"table {len(y):,} rows, {y.sum():,} clicks, {b.sum():,} purchases, {len(FEATURES)} inputs, in {time.time() - start:.0f} s", flush=True)
    new = t > np.quantile(t, 0.8)
    click, buy = fit(X[~new], y[~new], b[~new])
    Xn, yn, bn, gn = X[new], y[new], b[new], g[new]
    X1 = Xn.copy()
    if "slot" in FEATURES:
        X1[:, FEATURES.index("slot")] = 1  # every candidate scored at slot 1, as live
    first, top3, n = ranked(click.predict(X1) * buy.predict(X1), bn, gn)
    print(f"newest 20%: click AUC {auc(yn, click.predict(Xn)):.3f}, buy | click AUC {auc(bn[yn == 1], buy.predict(Xn[yn == 1])):.3f}; "
          f"purchased product first {first:.1f}%, top 3 {top3:.1f}% of {n} requests", flush=True)
    MODEL.parent.mkdir(exist_ok=True)
    for path, model in zip((MODEL, BUY_MODEL), fit(X, y, b)):
        tmp = path.with_suffix(".tmp")
        model.save_model(str(tmp))
        tmp.replace(path)
    print(f"saved {MODEL.name}, {BUY_MODEL.name} in {time.time() - start:.0f} s", flush=True)


def run(every: int = 0) -> None:
    from q2q.state import State
    state = State()
    state.load()
    while True:
        train(state)
        if not every:
            return
        time.sleep(every)


if __name__ == "__main__":
    run(int(sys.argv[1]) if len(sys.argv) > 1 else 0)
