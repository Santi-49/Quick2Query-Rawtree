"""Train ranker7's purchase model on the organic stream: did a shopper buy a product later today after viewing it.

    uv run python -m q2q.train7            # every event up to now
    uv run python -m q2q.train7 "2026-11-14 18:02:04"   # only events before this UTC time (holdout)

Rows: one per (shopper, product viewed today), at the last view before the first purchase of that product (label 1)
or at its last view (label 0). Views in the last 30 minutes before the cut open no row (their outcome is not known
yet); products already bought are skipped. Positives come from every shopper, negatives from a 1/16 sample of
shoppers (cityHash64 % 64 < 4), which shifts the base rate, not the ranking.
Features are ranker2's as of the view: the session's earlier views as recent views (last 6), the shopper's earlier
views today, history shopper features (live=False), slot 1, page 'product'. Fitted with early stopping on the newest
20% by view time, then refitted on everything.
Only ~7% of organic purchases follow a view of the same product by the same shopper today.
"""
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import lightgbm as lgb
import numpy as np

from q2q import rt
from q2q.strategies import ranker2, ranker7
from q2q.strategy import Request
from q2q.train import PARAMS, auc

CHUNKS = 16
SAMPLE = 4  # of 64: shoppers whose negatives are kept
RECENT = 6  # recent views per request at most (shop.requests: 0 to 6)
TODAY_KEEP = 10
UNKNOWN_MS = 30 * 60 * 1000
EVENTS = """SELECT user_id::String AS u, any(cityHash64(user_id::String) % 64 < {S}) AS sampled, any(device::String) AS dev, any(region::String) AS reg,
       groupArray(toUnixTimestamp64Milli(ts::DateTime64(3, 'UTC'))) AS tss, groupArray(event_type::String) AS et,
       groupArray(product_id::String) AS ps, groupArray(session_id::String) AS ss
FROM shop.events
WHERE event_type::String IN ('view', 'purchase') AND ts::DateTime64(3) < toDateTime64('{CUT}', 3) AND cityHash64(user_id::String) % {N} = {K}
  AND (cityHash64(user_id::String) % 64 < {S} OR user_id::String IN (
      SELECT b.u FROM (SELECT user_id::String AS u, product_id::String AS p, min(ts::DateTime64(3)) AS bt FROM shop.events
                       WHERE event_type::String = 'purchase' AND ts::DateTime64(3) < toDateTime64('{CUT}', 3) AND cityHash64(user_id::String) % {N} = {K}
                       GROUP BY u, p) b
      INNER JOIN (SELECT user_id::String AS u, product_id::String AS p, min(ts::DateTime64(3)) AS vt FROM shop.events
                  WHERE event_type::String = 'view' AND ts::DateTime64(3) < toDateTime64('{CUT}', 3) AND cityHash64(user_id::String) % {N} = {K}
                  GROUP BY u, p) v ON b.u = v.u AND b.p = v.p
      WHERE v.vt < b.bt))
GROUP BY u"""


def examples(u: str, new: bool, dev: str, reg: str, events: list, end_ms: int, negatives: bool) -> list:
    """(Request, today, product, label, view ms) per product viewed. events: (ms, type, product, session), time order."""
    session, today, bought, open_, out = {}, [], set(), {}, []
    for t, et, p, s in events:
        if et == "purchase":
            if p in open_ and p not in bought:
                req, seen, ms = open_.pop(p)
                out.append((req, seen, p, 1, ms))
            bought.add(p)
            continue
        if p not in bought and t < end_ms:
            open_[p] = (Request("", t / 1000, u, new, "product", dev, reg, session.get(s, [])[-RECENT:]), today[-TODAY_KEEP:], t)
        session[s] = session.get(s, []) + [p]
        today = [x for x in today if x != p] + [p]
    return out + ([(req, seen, p, 0, ms) for p, (req, seen, ms) in open_.items()] if negatives else [])


def pull(cut: str) -> list[dict]:
    sql = EVENTS.replace("{CUT}", cut).replace("{N}", str(CHUNKS)).replace("{S}", str(SAMPLE))
    with ThreadPoolExecutor(4) as pool:
        return [r for part in pool.map(lambda k: rt.query(sql.replace("{K}", str(k)), timeout=120), range(CHUNKS)) for r in part]


def table(state, cut: str):
    """X, label, view time over the organic rows before cut."""
    from q2q.state import epoch
    end_ms = int(epoch(cut) * 1000) - UNKNOWN_MS
    X, y, t = [], [], []
    for r in pull(cut):
        u = r["u"]
        events = sorted(zip(map(int, r["tss"]), r["et"], r["ps"], r["ss"]))
        for req, today, pid, label, ms in examples(u, u not in state._user_row, r["dev"], r["reg"], events, end_ms, bool(r["sampled"])):
            p = state.products.get(pid)
            if p is None:
                continue
            c = ranker2.context(req, state, live=False, today=today)
            if pid in c["bought"]:
                continue
            X.append(ranker2.features(p, 1, req, c))
            y.append(label)
            t.append(ms)
    return np.array(X, dtype=float), np.array(y, dtype=int), np.array(t)


def train(state, cut: str | None = None):
    """Fit and save ranker7_buy on organic rows before cut (default: now). Returns the model."""
    start = time.time()
    cut = cut or rt.query("SELECT toString(max(ts::DateTime64(3))) AS m FROM shop.events")[0]["m"][:19]
    X, y, t = table(state, cut)
    print(f"organic table before {cut}: {len(y):,} rows, {y.sum():,} purchases after a view, in {time.time() - start:.0f} s", flush=True)
    new = t > np.quantile(t, 0.8)
    m = lgb.train(PARAMS, lgb.Dataset(X[~new], y[~new], feature_name=ranker2.FEATURES), num_boost_round=2000,
                  valid_sets=[lgb.Dataset(X[new], y[new])], callbacks=[lgb.early_stopping(100, verbose=False)])
    rounds = max(m.best_iteration, 50)
    print(f"newest 20% by view time: organic buy AUC {auc(y[new], m.predict(X[new], num_iteration=m.best_iteration)):.3f}, {rounds} rounds", flush=True)
    model = lgb.train(PARAMS, lgb.Dataset(X, y, feature_name=ranker2.FEATURES), num_boost_round=rounds)
    gain = model.feature_importance("gain")
    print("importance: " + ", ".join(f"{ranker2.FEATURES[i]} {100 * gain[i] / gain.sum():.0f}%" for i in np.argsort(-gain)[:10]), flush=True)
    ranker7.BUY_MODEL.parent.mkdir(parents=True, exist_ok=True)
    tmp = ranker7.BUY_MODEL.with_suffix(".tmp")
    model.save_model(str(tmp))
    tmp.replace(ranker7.BUY_MODEL)
    print(f"saved {ranker7.BUY_MODEL.name} in {time.time() - start:.0f} s", flush=True)
    return model


if __name__ == "__main__":
    from q2q.state import State
    st = State()
    st.load()
    train(st, sys.argv[1] if len(sys.argv) > 1 else None)
