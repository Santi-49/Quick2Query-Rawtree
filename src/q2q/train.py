"""Train the ranker on our live feedback: one row per impression, label = clicked.

    q2q train            # once
    q2q train 1800       # again every 1800 s

Validation is by time: the model is fitted on the first 80% of requests and scored on the newest 20%.
The saved model is then refitted on everything.
"""
import time
from concurrent.futures import ThreadPoolExecutor

import lightgbm as lgb
import numpy as np

from q2q import rt
from q2q.strategies.ranker import FEATURES, MODEL, context, features
from q2q.strategy import Request

ROWS = """
SELECT f.rid AS rid, f.shown AS shown, f.clicked AS clicked, r.user_id AS user_id, r.new AS new, r.page AS page,
       r.device AS device, r.region AS region, r.views AS views, r.t AS t
FROM (SELECT request_id::String AS rid, any(shown::Array(String)) AS shown, any(clicked::String) AS clicked
      FROM {TEAM}.feedback WHERE cityHash64(request_id::String) % {N} = {K} GROUP BY rid) f
INNER JOIN (SELECT request_id::String AS rid, any(user_id::String) AS user_id, any(is_new_user::Bool) AS new, any(context.page::String) AS page,
                   any(context.device::String) AS device, any(context.region::String) AS region,
                   any(arrayMap(v -> v.product_id::String, recent_views::Array(JSON))) AS views, any(toUnixTimestamp64Milli(ts::DateTime64(3, 'UTC'))) AS t
            FROM shop.requests WHERE cityHash64(request_id::String) % {N} = {K} GROUP BY rid) r ON r.rid = f.rid"""
PARAMS = {"objective": "binary", "learning_rate": 0.05, "num_leaves": 15, "min_data_in_leaf": 200, "feature_fraction": 0.8,
          "lambda_l2": 10.0, "verbose": -1, "num_threads": 2}
CHUNKS = 8


def table(state):
    """X, y, request time and request index per impression. Products the shopper bought in history are left out,
    as the ranker never shows them. Live purchases are ignored here: they would leak the outcome into the features."""
    with ThreadPoolExecutor(4) as pool:
        rows = [r for part in pool.map(lambda k: rt.query(ROWS.replace("{N}", str(CHUNKS)).replace("{K}", str(k)), timeout=120), range(CHUNKS)) for r in part]
    rows.sort(key=lambda r: r["t"])
    X, y, t, g = [], [], [], []
    for i, r in enumerate(rows):
        req = Request(r["rid"], r["t"] / 1000, r["user_id"], bool(r["new"]), r["page"], r["device"], r["region"], list(r["views"]))
        c = context(req, state, live_purchases=False)
        for slot, pid in enumerate(r["shown"], 1):
            p = state.products.get(pid)
            if p is not None and pid not in c["bought"]:
                X.append(features(p, slot, req, c))
                y.append(pid == r["clicked"])
                t.append(r["t"])
                g.append(i)
    return np.array(X, dtype=float), np.array(y, dtype=int), np.array(t), np.array(g)


def auc(y, s) -> float:
    order = np.argsort(s)
    ranks = np.empty(len(s))
    ranks[order] = np.arange(1, len(s) + 1)
    pos = y.sum()
    return (ranks[y == 1].sum() - pos * (pos + 1) / 2) / (pos * (len(y) - pos))


def train(state) -> None:
    start = time.time()
    X, y, t, g = table(state)
    cut = np.quantile(t, 0.8)
    old, new = t <= cut, t > cut
    model = lgb.train(PARAMS, lgb.Dataset(X[old], y[old], feature_name=FEATURES), num_boost_round=300)
    pred = model.predict(X[new])
    slot_only = 1 / np.log2(X[new][:, 0] + 1)
    hits = [y[new][g[new] == i][np.argmax(pred[g[new] == i])] for i in np.unique(g[new][y[new] == 1])]
    print(f"rows {len(y):,} clicks {y.sum():,} | newest 20%: AUC {auc(y[new], pred):.3f} (slot alone {auc(y[new], slot_only):.3f}), "
          f"top-scored item is the clicked one in {100 * np.mean(hits):.0f}% of clicked requests", flush=True)
    gain = model.feature_importance("gain")
    print("importance: " + ", ".join(f"{FEATURES[i]} {100 * gain[i] / gain.sum():.0f}%" for i in np.argsort(-gain)[:10]), flush=True)
    final = lgb.train(PARAMS, lgb.Dataset(X, y, feature_name=FEATURES), num_boost_round=300)
    MODEL.parent.mkdir(exist_ok=True)
    tmp = MODEL.with_suffix(".tmp")
    final.save_model(str(tmp))
    tmp.replace(MODEL)
    print(f"saved {MODEL.name} in {time.time() - start:.0f} s", flush=True)


def run(every: int = 0) -> None:
    from q2q.state import State
    state = State()
    state.load()
    while True:
        train(state)
        if not every:
            return
        time.sleep(every)
