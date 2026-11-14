"""H-loglinear: logistic regression of click and purchase-given-click on clean 0/1 indicators (linear1.indicators).

    uv run python eda/linear/fit.py            # pull feedback to now, fit, compare, write models/linear1.json
    uv run python eda/linear/fit.py --cached   # reuse data/linear/pull.pkl

Rows as train2: one per shown product per feedback request, history-bought products left out, today's views from
shop.events before the request. Added at request time: our clicks earlier today (not bought), purchases earlier
today (ours and organic), price cuts from catalog_updates. Held out: the newest 20% of requests.
"""
import bisect
import json
import math
import pickle
import sys
import time

import lightgbm as lgb
import numpy as np
from sklearn.linear_model import LogisticRegression

from q2q import rt
from q2q.state import State
from q2q.strategies import linear1, ranker2, rules4
from q2q.strategy import Request
from q2q.train import PARAMS, auc
from q2q.train2 import ROWS2, TODAY, TODAY_KEEP, fit_buy, pulled, ranked

OUT = rt.ROOT / "data" / "linear"
BUYS = TODAY.replace("'view'", "'purchase'")
CUTS = """SELECT product_id::String AS p, toUnixTimestamp64Milli(ts::DateTime64(3, 'UTC')) AS t, price_eur::Float64 AS price
FROM shop.catalog_updates WHERE change::String = 'price_change' ORDER BY t"""
ROUND = [0.25, 0.33, 0.5, 0.67, 0.75, 1, 1.25, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10, 12, 15, 20]
NS = len(linear1.NAMES)


def pull(cached: bool):
    path = OUT / "pull.pkl"
    if cached and path.exists():
        return pickle.loads(path.read_bytes())
    d = {"rows": pulled(ROWS2), "today": pulled(TODAY), "buys": pulled(BUYS), "cuts": rt.query(CUTS)}
    OUT.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pickle.dumps(d))
    return d


def by_user(rows):
    """user -> (times sorted, products)."""
    out = {}
    for r in rows:
        pairs = sorted(zip(map(int, r["ts"]), r["ps"]))
        out[r["u"]] = ([t for t, _ in pairs], [p for _, p in pairs])
    return out


class CutAt:
    """Price cut ratios at one moment, read like state.price_cut."""
    def __init__(self, cuts, base, t):
        self.cuts, self.base, self.t = cuts, base, t

    def get(self, pid, default=1.0):
        ts, prices = self.cuts.get(pid, ((), ()))
        i = bisect.bisect_right(ts, self.t)
        return min(1.0, prices[i - 1] / self.base[pid]) if i and pid in self.base else default


def rules4_score(p, c) -> float:
    """rules4.explain's product without trend and price cut, from a ranker2 context."""
    views, s = c["views"], c["shopper"]
    relation = {}
    for i, v in enumerate(reversed(views)):
        last, first = i == 0, i == len(views) - 1
        for key, value in ((v.id, rules4.FIRST_VIEW if first else rules4.OTHER_VIEW), (v.subcategory, rules4.SUBCATEGORY[not last]),
                           (v.category, rules4.CATEGORY_MAIN if v.category == c["main"] else rules4.CATEGORY_OTHER)):
            relation[key] = max(relation.get(key, 0.0), value)
    session = relation.get(p.id) or relation.get(p.subcategory) or relation.get(p.category) or 1.0
    before = rules4.CARTED if s and p.id in s.carted else rules4.VIEWED_ONLY
    share_w = rules4.SHARE_SESSION if views else rules4.SHARE_HOME
    damp = 0.5 if c["known"] else 1.0
    return (p.appeal * (max(session, before) if before > 1 else session) * (rules4.BOTH if session > 1 and before > 1 else 1.0)
            * (1 + share_w * c["shares"].get(p.category, 0.0)) * (1 + damp * (c["segment"].get(p.category, 1.0) - 1)))


def table(state, d):
    rows = sorted(d["rows"], key=lambda r: r["t"])
    today, buys = by_user(d["today"]), by_user(d["buys"])
    cuts = {}
    for r in d["cuts"]:
        ts, ps = cuts.setdefault(r["p"], ([], []))
        ts.append(int(r["t"]))
        ps.append(float(r["price"]))
    clicks = {}  # user -> [(t, clicked, purchased)]
    for r in rows:
        if r["clicked"]:
            clicks.setdefault(r["user_id"], []).append((r["t"], r["clicked"], r["purchased"]))
    known = [state.shopper(u, live=False) for u in {r["user_id"] for r in rows}]
    high = float(np.median([s.cart_rate for s in known if s and s.cat_share]))
    L, R, y, b, t, g, r4 = [], [], [], [], [], [], []
    for i, r in enumerate(rows):
        req = Request(r["rid"], r["t"] / 1000, r["user_id"], bool(r["new"]), r["page"], r["device"], r["region"], list(r["views"]))
        ts, ps = today.get(r["user_id"], ([], []))
        bts, bps = buys.get(r["user_id"], ([], []))
        earlier = [(p, q) for tt, p, q in clicks.get(r["user_id"], ()) if tt < r["t"]]
        bought = set(bps[:bisect.bisect_left(bts, int(r["t"]))]) | {q for _, q in earlier if q}
        c = linear1.context(req, state, live=False, today=ps[:bisect.bisect_left(ts, int(r["t"]))][-TODAY_KEEP:],
                            our_clicks={p for p, q in earlier if p != q}, bought_today=bought,
                            cut=CutAt(cuts, state._base_price, int(r["t"])), cart_high=high)
        for slot, pid in enumerate(r["shown"], 1):
            p = state.products.get(pid)
            if p is not None and pid not in c["bought"]:
                L.append(linear1.indicators(p, slot, req, c))
                R.append(ranker2.features(p, slot, req, c))
                r4.append(rules4_score(p, c))
                y.append(pid == r["clicked"])
                b.append(pid == r["clicked"] and pid == r["purchased"])
                t.append(r["t"])
                g.append(i)
    a = lambda v, dt=float: np.array(v, dtype=dt)  # noqa: E731
    return a(L), a(R), a(y, int), a(b, int), a(t), a(g, int), a(r4), high


def logit(X, y, C=1.0):
    return LogisticRegression(C=C, max_iter=3000).fit(X, y)


def at_slot1(X):
    X1 = X.copy()
    X1[:, :9] = 0
    return X1


def nearest(m):
    r = min(ROUND, key=lambda x: abs(math.log(m / x)))
    return f"~{r:g}" if abs(m / r - 1) <= 0.10 else ""


def report(title, models, X, n):
    print(f"\n## {title}\n{'indicator':<22}{'n=1':>9}{'all':>8}{'half1':>8}{'half2':>8}  stable  round")
    for j, name in enumerate(linear1.NAMES):
        m = [math.exp(mod.coef_[0][j]) for mod in models]
        stable = max(m[1], m[2]) / min(m[1], m[2]) <= 1.25
        count = int((X[:, j] > 0).sum()) if name != "log_appeal" else len(X)
        print(f"{name:<22}{count:>9}{m[0]:>8.2f}{m[1]:>8.2f}{m[2]:>8.2f}  {'yes' if stable else 'no ':<6}  {nearest(m[0])}")
    print(f"{'intercept (odds)':<22}{'':>9}" + "".join(f"{math.exp(mod.intercept_[0]):>8.4f}" for mod in models))


def main():
    start = time.time()
    state = State()
    state.load()
    d = pull("--cached" in sys.argv)
    X, XR, y, b, t, g, r4, high = table(state, d)
    print(f"table {len(y):,} rows, {y.sum():,} clicks, {b.sum():,} purchases, {len(np.unique(g)):,} requests; "
          f"high cart rate >= {high:.4f}; {time.time() - start:.0f} s", flush=True)

    # 1. coefficients: all, first half, second half by request time
    half = t <= np.median(t)
    clk = [logit(X[m], y[m]) for m in (np.ones(len(y), bool), half, ~half)]
    k = y == 1
    buy = [logit(X[m & k], b[m & k]) for m in (np.ones(len(y), bool), half, ~half)]
    report("click: multiplier exp(coef) on the odds", clk, X, len(y))
    report("purchase | click: multiplier exp(coef) on the odds", buy, X[k], k.sum())

    # 2. held out: newest 20% of requests
    new = t > np.quantile(t, 0.8)
    old = ~new
    lc, lb = logit(X[old], y[old]), logit(X[old & k], b[old & k])
    rc = lgb.train(PARAMS, lgb.Dataset(XR[old], y[old], feature_name=ranker2.FEATURES), num_boost_round=300)
    rb = fit_buy(XR[old & k], b[old & k])
    Xn, XRn, yn, bn, gn = X[new], XR[new], y[new], b[new], g[new]
    kn = yn == 1
    lin_click, lin_buy = lc.predict_proba(Xn)[:, 1], lc.predict_proba(Xn)[:, 1] * lb.predict_proba(Xn)[:, 1]
    r2_click = rc.predict(XRn)
    r2_buy = r2_click * rb.predict(XRn)
    XR1 = XRn.copy()
    XR1[:, 0] = 1
    X1 = at_slot1(Xn)
    w = 1 / np.log2(XRn[:, 0] + 1)
    scores = {"linear (logit)": (lin_click, lin_buy, lb.predict_proba(Xn)[:, 1], lc.predict_proba(X1)[:, 1] * lb.predict_proba(X1)[:, 1]),
              "ranker2 (LightGBM)": (r2_click, r2_buy, rb.predict(XRn), rc.predict(XR1) * rb.predict(XR1)),
              "rules4 score": (r4[new] * w, r4[new] * w, r4[new], r4[new])}
    print(f"\n## held out: newest 20% ({len(np.unique(gn)):,} requests, {yn.sum()} clicks, {bn.sum()} purchases)")
    print(f"{'model':<20}{'click AUC':>10}{'buy AUC':>9}{'buy|click':>10}{'first %':>9}{'top3 %':>8}")
    for name, (sc, sb, sbc, s1) in scores.items():
        first, top3, n = ranked(s1, bn, gn)
        print(f"{name:<20}{auc(yn, sc):>10.3f}{auc(bn, sb):>9.3f}{auc(bn[kn], sbc[kn]):>10.3f}{first:>9.1f}{top3:>8.1f}   (n={n})")

    # 3. coefficients for the strategy, fitted on everything
    linear1.COEFS.parent.mkdir(exist_ok=True)
    m = {"names": linear1.NAMES, "click": clk[0].coef_[0].tolist(), "click_intercept": float(clk[0].intercept_[0]),
         "buy": buy[0].coef_[0].tolist(), "buy_intercept": float(buy[0].intercept_[0]), "cart_rate_high": high,
         "rows": int(len(y)), "clicks": int(y.sum()), "purchases": int(b.sum()), "fitted": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())}
    tmp = linear1.COEFS.with_suffix(".tmp")
    tmp.write_text(json.dumps(m, indent=1), encoding="utf-8")
    tmp.replace(linear1.COEFS)
    print(f"\nsaved {linear1.COEFS.name} in {time.time() - start:.0f} s")


if __name__ == "__main__":
    main()
