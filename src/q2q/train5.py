"""Train ranker5: train2's rows and recipe, plus the product-embedding cosines of ranker5.

    uv run python -m q2q.train5          # once (needs data/emb/, from python -m q2q.emb)
    uv run python -m q2q.train5 1800     # again every 1800 s

Inputs are taken as of the request (today's views before it, history-only shopper), as train2. The embedding is a
fixed product table; it is built from history and today's events up to its build time. Validation as train3: oldest
80% fitted, newest 20% scored, against ranker2's features on the same rows.
"""
import bisect
import sys
import time

import numpy as np

from q2q.strategies import ranker2, ranker5
from q2q.strategies.ranker5 import FEATURES, context, embedding, features
from q2q.strategy import Request
from q2q.train import auc
from q2q.train2 import ROWS2, TODAY, TODAY_KEEP, pulled, ranked
from q2q.train3 import fit

MODEL, BUY_MODEL = ranker5.MODEL, ranker5.BUY_MODEL
N2 = len(ranker2.FEATURES)


def table(state):
    """X, click, buy, request time and request index per impression."""
    emb = embedding()
    rows = sorted(pulled(ROWS2), key=lambda r: r["t"])
    today = {}
    for r in pulled(TODAY):
        pairs = sorted(zip(map(int, r["ts"]), r["ps"]))
        today[r["u"]] = ([t for t, _ in pairs], [p for _, p in pairs])
    X, y, b, t, g = [], [], [], [], []
    for i, r in enumerate(rows):
        req = Request(r["rid"], r["t"] / 1000, r["user_id"], bool(r["new"]), r["page"], r["device"], r["region"], list(r["views"]))
        ts, ps = today.get(r["user_id"], ([], []))
        c = context(req, state, live=False, today=ps[:bisect.bisect_left(ts, int(r["t"]))][-TODAY_KEEP:], emb=emb)
        for slot, pid in enumerate(r["shown"], 1):
            p = state.products.get(pid)
            if p is not None and pid not in c["bought"]:
                X.append(features(p, slot, req, c))
                y.append(pid == r["clicked"])
                b.append(pid == r["clicked"] and pid == r["purchased"])
                t.append(r["t"])
                g.append(i)
    return np.array(X, dtype=float), np.array(y, dtype=int), np.array(b, dtype=int), np.array(t), np.array(g)


def train(state) -> None:
    start = time.time()
    X, y, b, t, g = table(state)
    print(f"table {len(y):,} rows, {y.sum():,} clicks, {b.sum():,} purchases in {time.time() - start:.0f} s; "
          f"embedding known for {100 * np.isfinite(X[:, N2]).mean():.0f}% of rows (recent views), {100 * np.isfinite(X[:, N2 + 3]).mean():.0f}% (profile)", flush=True)
    new = t > np.quantile(t, 0.8)
    old = ~new
    m5, m2 = fit(X[old], y[old], b[old], FEATURES), fit(X[old][:, :N2], y[old], b[old], ranker2.FEATURES)
    Xn, yn, bn, gn = X[new], y[new], b[new], g[new]
    kn = yn == 1
    X1 = Xn.copy()
    X1[:, 0] = 1
    for name, (click, buy), cols in (("ranker2 features", m2, N2), ("ranker5", m5, len(FEATURES))):
        first, top3, n = ranked(click.predict(X1[:, :cols]) * buy.predict(X1[:, :cols]), bn, gn)
        print(f"newest 20% {name}: click AUC {auc(yn, click.predict(Xn[:, :cols])):.3f}, buy | click AUC {auc(bn[kn], buy.predict(Xn[kn][:, :cols])):.3f} "
              f"on {kn.sum()} clicks; purchased product first {first:.1f}%, top 3 {top3:.1f}% of {n} requests", flush=True)
    for label, model, k in (("click", m5[0], 12), ("buy", m5[1], 8)):
        gain = model.feature_importance("gain")
        print(f"{label} importance: " + ", ".join(f"{FEATURES[i]} {100 * gain[i] / gain.sum():.1f}%" for i in np.argsort(-gain)[:k]), flush=True)
    MODEL.parent.mkdir(parents=True, exist_ok=True)
    for path, model in zip((MODEL, BUY_MODEL), fit(X, y, b, FEATURES)):
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
