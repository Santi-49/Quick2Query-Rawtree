"""H-gap aggregates over data/gap/*.parquet (see build.py). Prints markdown tables.

    uv run python eda/gap/report.py [q1 q2 q3 q4 q5 q6]
"""
import sys

import numpy as np
import pandas as pd

from q2q import rt

OUT = rt.ROOT / "data" / "gap"
ROUTES = ["ret_views", "new_views", "ret_home", "new_home"]
imp = pd.read_parquet(OUT / "imp.parquet")
req = pd.read_parquet(OUT / "req.parquet")
org = pd.read_parquet(OUT / "org.parquet")
CLASSES = ["bought", "rv_only", "rv_first", "rv_last", "rv_other", "cart_today", "viewed_today", "hist_cart", "hist_view",
           "same_sub", "same_cat", "fav_cat", "none"]


def rate(d):
    return pd.Series({"imps": len(d), "sw": d.w.sum(), "buys": d.buy.sum(), "clicks": d.click.sum(),
                      "wconv%": 100 * d.buy.sum() / d.w.sum() if len(d) else np.nan})


def q1():
    print("## Q1 purchases by class and route: buys (share of route's buys) | wconv% per slot-weighted impression | Σw")
    for rt_ in ROUTES:
        d = imp[imp.route == rt_]
        g = d.groupby("cls").apply(rate, include_groups=False).reindex(CLASSES).fillna(0)
        tot = g.buys.sum()
        print(f"\n### {rt_}: {d.request_id.nunique()} requests, {int(tot)} buys, {100 * tot / d.request_id.nunique():.2f}% per request")
        print("| class | buys | share | wconv% | Σw | clicks |")
        print("|---|---|---|---|---|---|")
        for c, x in g.iterrows():
            print(f"| {c} | {int(x.buys)} | {100 * x.buys / tot:.0f}% | {x['wconv%']:.2f} | {x.sw:.0f} | {int(x.clicks)} |")


def q2():
    print("## Q2 what we miss: per class, share of requests with such a product available, shown at all, at slot 1, top 3; lost buys / 1,000 requests")
    p1 = {}
    for rt_ in ROUTES:
        d = imp[(imp.route == rt_) & (imp.slot == 1)]
        p1[rt_] = d.buy.sum() / len(d)  # value of what we put at slot 1 now
    rows = []
    for c in ("rv_only", "rv_first", "rv_last", "rv_other", "cart_today", "viewed_today", "hist_cart"):
        for rt_ in ROUTES:
            d = imp[(imp.route == rt_) & (imp.cls == c)]
            if d.buy.sum() < 3:
                continue
            p = d.buy.sum() / d.w.sum()
            r = req[req.route == rt_]
            has = r[r["has_" + c] > 0]
            slot = has["slot_" + c]
            w = np.where(slot > 0, 1 / np.log2(slot.clip(lower=1) + 1), 0)
            lost = (np.clip(p - p1[rt_], 0, None) * (1 - w)).sum() / len(r) * 1000  # move it to slot 1, displacing today's slot 1
            rows.append((c, rt_, len(r), len(has) / len(r), (slot > 0).mean() if len(has) else 0, (slot == 1).mean() if len(has) else 0,
                         ((slot > 0) & (slot <= 3)).mean() if len(has) else 0, 100 * p, int(d.buy.sum()), 100 * p1[rt_], lost))
    rows.sort(key=lambda x: -x[-1])
    print("| class | route | requests | has it | shown | slot 1 | top 3 | wconv% | buys | slot-1 now % | lost / 1,000 req |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for x in rows:
        print(f"| {x[0]} | {x[1]} | {x[2]} | {100 * x[3]:.1f}% | {100 * x[4]:.0f}% | {100 * x[5]:.0f}% | {100 * x[6]:.0f}% | {x[7]:.2f} | {x[8]} | {x[9]:.2f} | {x[10]:.2f} |")
    print("\nper arm, cart_today and rv_first (routes pooled): share shown in top 3 when available")
    m = req.merge(imp[imp.slot == 1][["request_id"]], on="request_id")
    for c in ("cart_today", "rv_first", "hist_cart"):
        has = m[m["has_" + c] > 0]
        t = has.groupby("mv").apply(lambda x: pd.Series({"n": len(x), "top3": ((x["slot_" + c] > 0) & (x["slot_" + c] <= 3)).mean(),
                                                         "slot1": (x["slot_" + c] == 1).mean()}), include_groups=False)
        print(c, t[t.n > 200].round(2).to_dict("index"))


def q3():
    print("## Q3 organic purchases in the 10 minutes after a request where we sold nothing")
    for rt_ in ROUTES:
        o = org[org.route == rt_]
        n_req = ((req.route == rt_) & (req.bought == 0)).sum()
        print(f"\n### {rt_}: {len(o)} organic purchases after {n_req} unsold requests ({100 * o.request_id.nunique() / n_req:.1f}% of them)")
        print("class:", (o.cls.value_counts(normalize=True) * 100).round(1).to_dict())
        print("caught by a top-10 list:", {k[3:]: round(100 * o[k].mean(), 1) for k in o.columns if k.startswith("in_")})


def q4():
    print("## Q4 timing and state (rv_* and cart classes); buys / Σw, only cells with >= 30 buys in the factor")
    rv = imp[imp.cls.str.startswith("rv_")]
    cart = imp[imp.cls.isin(["cart_today", "hist_cart"])]

    def show(name, d, col, bins):
        d = d.assign(b=pd.cut(d[col], bins))
        g = d.groupby("b", observed=True).apply(rate, include_groups=False)
        if g.buys.sum() >= 30:
            print(f"\n{name} by {col} ({int(g.buys.sum())} buys)")
            print(g[["imps", "sw", "buys", "wconv%"]].round(2).to_string())

    show("recent views", rv, "n_ev", [-1, 0, 5, 20, 50, 1e9])
    show("cart today", imp[imp.cls == "cart_today"], "min_since_cart", [0, 10, 30, 60, 120, 1e9])
    show("cart today", imp[imp.cls == "cart_today"], "n_ev", [-1, 5, 20, 50, 1e9])
    show("viewed today", imp[imp.cls == "viewed_today"], "today_views", [0, 1, 2, 4, 1e9])
    show("cart today", imp[imp.cls == "cart_today"], "today_views", [-1, 0, 1, 2, 4, 1e9])
    show("recent views", rv, "price_rel_usual", [0, 0.5, 0.8, 1.25, 2, 1e9])
    show("carts", cart, "price_rel_usual", [0, 0.5, 0.8, 1.25, 2, 1e9])
    show("recent views", rv, "price_vs_base", [0, 0.95, 1.05, 10])
    show("carts", cart, "price_vs_base", [0, 0.95, 1.05, 10])
    show("cart today + viewed today", imp[imp.cls.isin(["cart_today", "viewed_today"])], "price_since_view", [0, 0.97, 1.03, 10])
    show("hist carts", imp[imp.cls == "hist_cart"], "hist_carts", [0, 1, 2, 100])
    show("recent views", rv, "sec_since_last_view", [0, 15, 30, 60, 120, 1e9])
    print("\nslot curve: wconv-normalised buys per impression, relative to 1/log2(k+1), by class group")
    for name, d in (("recent views", rv), ("carts", cart), ("all", imp)):
        g = d.groupby("slot").agg(n=("buy", "size"), b=("buy", "sum"), w=("w", "first"))
        g["per_imp%"] = 100 * g.b / g.n
        g["per_w%"] = g["per_imp%"] / g.w
        print(name, int(g.b.sum()), "buys")
        print(g.round(3).T.to_string())
    print("\nbuys by slot, all imps: share in slot 1 / 1-3:", round(imp[imp.buy == 1].slot.eq(1).mean(), 3), round(imp[imp.buy == 1].slot.le(3).mean(), 3))


def q5():
    print("## Q5 home")
    for rt_ in ("ret_home", "new_home"):
        o = org[org.route == rt_]
        print(rt_, "organic next purchase caught:", {k[3:]: round(100 * o[k].mean(), 1) for k in o.columns if k.startswith("in_")}, len(o))


def q6():
    print("## Q6 regularities")
    r = req.copy()
    r["hex0"] = r.request_id.str[2]
    r["ms"] = r.ts % 1000
    for col, f in (("hex0", None), ("ms", lambda s: pd.cut(s, [-1, 99, 499, 999])), ("hour", None)):
        x = r if col != "hour" else r.assign(hour=pd.to_datetime(r.ts, unit="ms").dt.hour)
        k = f(x[col]) if f else x[col]
        print(col, x.groupby(k, observed=True).bought.agg(["size", "mean"]).round(4).to_dict("index"))


if __name__ == "__main__":
    for q in sys.argv[1:] or ["q1", "q2", "q3", "q4", "q5", "q6"]:
        globals()[q]()
        print()
