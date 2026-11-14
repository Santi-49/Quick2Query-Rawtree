"""Train ranker3: ranker2's rows and models, plus today's carts, our earlier clicks and the H-loglinear inputs.

    q2q train3           # once
    q2q train3 1800      # again every 1800 s

Every added input is taken as of the request: carts and purchases from shop.events and our clicks and purchases
from feedback, all strictly before the request. Products bought earlier today are left out, as serving never shows
them. Validation as train2 (oldest 80% fitted, newest 20% scored) against ranker2's features on the same rows.
"""
import bisect
import time
from collections import Counter

import lightgbm as lgb
import numpy as np

from q2q.strategies import ranker2
from q2q.strategies.ranker3 import BUY_MODEL, FEATURES, MODEL, context, features
from q2q.strategy import Request
from q2q.train import PARAMS, auc
from q2q.train2 import ROWS2, SMALL, TODAY, TODAY_KEEP, pulled, ranked

USERS = "user_id::String IN (SELECT user_id::String FROM shop.requests WHERE request_id::String IN (SELECT request_id::String FROM {TEAM}.feedback))"
CARTS = f"""SELECT user_id::String AS u, groupArray(product_id::String) AS ps, groupArray(toUnixTimestamp64Milli(ts::DateTime64(3, 'UTC'))) AS ts
FROM shop.events WHERE event_type::String = 'add_to_cart' AND cityHash64(user_id::String) % {{N}} = {{K}} AND {USERS} GROUP BY u"""
BUYS = TODAY.replace("'view'", "'purchase'")  # first purchase time per (user, product)
N2 = len(ranker2.FEATURES)
TC = FEATURES.index("carted_today")


def by_user(rows) -> dict:
    """user -> (times sorted, products)."""
    out = {}
    for r in rows:
        pairs = sorted(zip(map(int, r["ts"]), r["ps"]))
        out[r["u"]] = ([t for t, _ in pairs], [p for _, p in pairs])
    return out


def table(state):
    """X, click, buy, request time and request index per impression."""
    rows = sorted(pulled(ROWS2), key=lambda r: r["t"])
    today, carts, buys = by_user(pulled(TODAY)), by_user(pulled(CARTS)), by_user(pulled(BUYS))
    fed = {}  # user -> [(t, clicked, purchased)] from our feedback, in time order
    for r in rows:
        if r["clicked"]:
            fed.setdefault(r["user_id"], []).append((r["t"], r["clicked"], r["purchased"]))
    X, y, b, t, g = [], [], [], [], []
    for i, r in enumerate(rows):
        now = int(r["t"])
        req = Request(r["rid"], now / 1000, r["user_id"], bool(r["new"]), r["page"], r["device"], r["region"], list(r["views"]))
        ts, ps = today.get(r["user_id"], ([], []))
        bts, bps = buys.get(r["user_id"], ([], []))
        earlier = [(p, q) for tt, p, q in fed.get(r["user_id"], ()) if tt < now]
        bought = set(bps[:bisect.bisect_left(bts, now)]) | {q for _, q in earlier if q}
        cts, cps = carts.get(r["user_id"], ([], []))
        k = bisect.bisect_left(cts, now)
        last = {p: tt / 1000 for tt, p in zip(cts[:k], cps[:k])}
        c = context(req, state, live=False, today=ps[:bisect.bisect_left(ts, now)][-TODAY_KEEP:], carts=dict(Counter(cps[:k])),
                    cart_last=last, our={p for p, q in earlier if p != q}, bought_today=bought)
        for slot, pid in enumerate(r["shown"], 1):
            p = state.products.get(pid)
            if p is not None and pid not in c["bought"]:
                X.append(features(p, slot, req, c))
                y.append(pid == r["clicked"])
                b.append(pid == r["clicked"] and pid == r["purchased"])
                t.append(now)
                g.append(i)
    return np.array(X, dtype=float), np.array(y, dtype=int), np.array(b, dtype=int), np.array(t), np.array(g)


def fit_buy(X, b, names):
    small = len(b) < 1500
    return lgb.train(SMALL if small else PARAMS, lgb.Dataset(X, b, feature_name=names), num_boost_round=100 if small else 300)


def fit(X, y, b, names):
    click = lgb.train(PARAMS, lgb.Dataset(X, y, feature_name=names), num_boost_round=300)
    return click, fit_buy(X[y == 1], b[y == 1], names)


def train(state) -> None:
    start = time.time()
    X, y, b, t, g = table(state)
    tc = X[:, TC] > 0
    print(f"table {len(y):,} rows, {y.sum():,} clicks, {b.sum():,} purchases in {time.time() - start:.0f} s; "
          f"carted today: {tc.sum():,} impressions, {y[tc].sum()} clicks, {b[tc].sum()} purchases "
          f"({100 * b[tc].mean():.2f}% per impression against {100 * b[~tc].mean():.2f}%)", flush=True)
    new = t > np.quantile(t, 0.8)
    old = ~new
    m3, m2 = fit(X[old], y[old], b[old], FEATURES), fit(X[old][:, :N2], y[old], b[old], ranker2.FEATURES)
    Xn, yn, bn, gn = X[new], y[new], b[new], g[new]
    kn = yn == 1
    X1 = Xn.copy()
    X1[:, 0] = 1  # every candidate scored at slot 1, as live
    for name, (click, buy), cols in (("ranker2 features", m2, N2), ("ranker3", m3, len(FEATURES))):
        first, top3, n = ranked(click.predict(X1[:, :cols]) * buy.predict(X1[:, :cols]), bn, gn)
        print(f"newest 20% {name}: click AUC {auc(yn, click.predict(Xn[:, :cols])):.3f}, buy | click AUC {auc(bn[kn], buy.predict(Xn[kn][:, :cols])):.3f} "
              f"on {kn.sum()} clicks; purchased product first {first:.1f}%, top 3 {top3:.1f}% of {n} requests", flush=True)
    for label, model, k in (("click", m3[0], 12), ("buy", m3[1], 8)):
        gain = model.feature_importance("gain")
        print(f"{label} importance: " + ", ".join(f"{FEATURES[i]} {100 * gain[i] / gain.sum():.1f}%" for i in np.argsort(-gain)[:k]), flush=True)
    MODEL.parent.mkdir(exist_ok=True)
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
