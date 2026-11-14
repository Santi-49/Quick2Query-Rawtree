"""Train ranker2 on our live feedback: a click model (one row per impression) and a purchase-given-click model
(one row per clicked impression, label = the clicked product was purchased), on the wider features.

    q2q train2           # once
    q2q train2 1800      # again every 1800 s

Validation is by time (oldest 80% of requests fitted, newest 20% scored), against the ranker's 21-feature click
model with its fixed 0.81 / 0.27 purchase rule fitted on the same rows. Both models are then refitted on everything.
Today's views come from shop.events views before each request, not from the State, which reflects now.
"""
import bisect
import time
from concurrent.futures import ThreadPoolExecutor

import lightgbm as lgb
import numpy as np

from q2q import rt
from q2q.strategies import ranker
from q2q.strategies.ranker2 import BUY_MODEL, FEATURES, MODEL, context, features
from q2q.strategy import Request
from q2q.train import CHUNKS, PARAMS, ROWS, auc

ROWS2 = ROWS.replace("any(clicked::String) AS clicked", "any(clicked::String) AS clicked, any(purchased::String) AS purchased") \
            .replace("f.clicked AS clicked,", "f.clicked AS clicked, f.purchased AS purchased,")
TODAY = """SELECT u, groupArray(p) AS ps, groupArray(t) AS ts FROM (
    SELECT user_id::String AS u, product_id::String AS p, min(toUnixTimestamp64Milli(ts::DateTime64(3, 'UTC'))) AS t FROM shop.events
    WHERE event_type::String = 'view' AND cityHash64(user_id::String) % {N} = {K}
      AND user_id::String IN (SELECT user_id::String FROM shop.requests WHERE request_id::String IN (SELECT request_id::String FROM {TEAM}.feedback))
    GROUP BY u, p) GROUP BY u"""
SMALL = {**PARAMS, "num_leaves": 7, "min_data_in_leaf": 50}  # purchase model under 1,500 clicked rows, 100 rounds
TODAY_KEEP = 10  # as State: the last 10 products viewed today
IN_VIEWS = ranker.FEATURES.index("in_views")


def pulled(sql: str) -> list[dict]:
    with ThreadPoolExecutor(4) as pool:
        return [r for part in pool.map(lambda k: rt.query(sql.replace("{N}", str(CHUNKS)).replace("{K}", str(k)), timeout=120), range(CHUNKS)) for r in part]


def table(state):
    """X, click, buy, request time and request index per impression (history purchases left out, as in train.py)."""
    rows = sorted(pulled(ROWS2), key=lambda r: r["t"])
    today = {}  # user -> (first-view times sorted, products)
    for r in pulled(TODAY):
        pairs = sorted(zip(map(int, r["ts"]), r["ps"]))
        today[r["u"]] = ([t for t, _ in pairs], [p for _, p in pairs])
    X, y, b, t, g = [], [], [], [], []
    for i, r in enumerate(rows):
        req = Request(r["rid"], r["t"] / 1000, r["user_id"], bool(r["new"]), r["page"], r["device"], r["region"], list(r["views"]))
        ts, ps = today.get(r["user_id"], ([], []))
        c = context(req, state, live=False, today=ps[:bisect.bisect_left(ts, int(r["t"]))][-TODAY_KEEP:])  # context drops the request's own views
        for slot, pid in enumerate(r["shown"], 1):
            p = state.products.get(pid)
            if p is not None and pid not in c["bought"]:
                X.append(features(p, slot, req, c))
                y.append(pid == r["clicked"])
                b.append(pid == r["clicked"] and pid == r["purchased"])
                t.append(r["t"])
                g.append(i)
    return np.array(X, dtype=float), np.array(y, dtype=int), np.array(b, dtype=int), np.array(t), np.array(g)


def fit_buy(X, b):
    small = len(b) < 1500
    return lgb.train(SMALL if small else PARAMS, lgb.Dataset(X, b, feature_name=FEATURES), num_boost_round=100 if small else 300)


def ranked(score, b, g) -> tuple[float, float, int]:
    """Over requests with a purchased impression: share where it scores first, share in the top 3, number of requests."""
    first, top3 = [], []
    for i in np.unique(g[b == 1]):
        s, hit = score[g == i], b[g == i]
        rank = int((s > s[hit == 1][0]).sum())
        first.append(rank == 0)
        top3.append(rank < 3)
    return 100 * np.mean(first), 100 * np.mean(top3), len(first)


def train(state) -> None:
    start = time.time()
    X, y, b, t, g = table(state)
    print(f"table {len(y):,} rows, {y.sum():,} clicks, {b.sum():,} purchases in {time.time() - start:.0f} s", flush=True)
    new = t > np.quantile(t, 0.8)
    old = ~new
    click21 = lgb.train(PARAMS, lgb.Dataset(X[old][:, :len(ranker.FEATURES)], y[old], feature_name=ranker.FEATURES), num_boost_round=300)
    click = lgb.train(PARAMS, lgb.Dataset(X[old], y[old], feature_name=FEATURES), num_boost_round=300)
    clicked = old & (y == 1)
    buy = fit_buy(X[clicked], b[clicked])
    Xn, yn, bn, gn = X[new], y[new], b[new], g[new]
    print(f"newest 20%: click AUC {auc(yn, click.predict(Xn)):.3f} (ranker's 21 features {auc(yn, click21.predict(Xn[:, :len(ranker.FEATURES)])):.3f}); "
          f"buy | click AUC {auc(bn[yn == 1], buy.predict(Xn[yn == 1])):.3f} on {(yn == 1).sum()} clicks "
          f"(0.81/0.27 rule {auc(bn[yn == 1], Xn[yn == 1][:, IN_VIEWS]):.3f}); fitted on {clicked.sum()} clicks", flush=True)
    X1 = Xn.copy()
    X1[:, 0] = 1  # every candidate scored at slot 1, as live
    old_score = click21.predict(X1[:, :len(ranker.FEATURES)]) * np.where(X1[:, IN_VIEWS] > 0, ranker.BUY_AFTER_CLICK[1], ranker.BUY_AFTER_CLICK[0])
    new_score = click.predict(X1) * buy.predict(X1)
    for name, score in (("ranker (0.81/0.27)", old_score), ("ranker2 (click x buy)", new_score)):
        first, top3, n = ranked(score, bn, gn)
        print(f"purchased product among the 10 shown, held-out requests with a purchase ({n}): {name} ranks it first {first:.0f}%, top 3 {top3:.0f}%", flush=True)
    gain = click.feature_importance("gain")
    print("click importance: " + ", ".join(f"{FEATURES[i]} {100 * gain[i] / gain.sum():.0f}%" for i in np.argsort(-gain)[:12]), flush=True)
    gain = buy.feature_importance("gain")
    print("buy importance: " + ", ".join(f"{FEATURES[i]} {100 * gain[i] / gain.sum():.0f}%" for i in np.argsort(-gain)[:8]), flush=True)
    MODEL.parent.mkdir(exist_ok=True)
    for path, model in ((MODEL, lgb.train(PARAMS, lgb.Dataset(X, y, feature_name=FEATURES), num_boost_round=300)),
                        (BUY_MODEL, fit_buy(X[y == 1], b[y == 1]))):
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
