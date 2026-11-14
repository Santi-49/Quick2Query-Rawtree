"""H-home-who: precision of each product class on our home lists, per slot-weighted impression (w = 1/log2(slot+1)).
Reads data/home/ (eda/home/pull.py) and data/user_history.npz.

    uv run eda/home/impressions.py
"""
import json
from collections import defaultdict

import numpy as np
import pandas as pd

from q2q import rt

D = rt.ROOT / "data" / "home"


def main():
    r = pd.read_parquet(D / "reqs.parquet").rename(columns={"r.rid": "rid", "r.u": "u"})
    h = r[(r.nrv == 0) & (r.served == "team")]
    H = dict(np.load(rt.ROOT / "data" / "user_history.npz"))
    hu = {u: i for i, u in enumerate(H["users"])}
    names = H["products"]
    cat = {p["product_id"]: p for p in json.load(open(rt.ROOT / "data" / "catalog.json"))}

    def per_user(df):
        return {u: (g.t.values, g.p.values) for u, g in df.sort_values("t").groupby("u")}
    carts, views, buys = (per_user(pd.read_parquet(D / f"{n}.parquet")) for n in ("carts", "views", "buys"))
    empty = (np.empty(0), np.empty(0, dtype=object))

    acc = defaultdict(lambda: [0.0, 0, 0])
    for x in h.itertuples():
        i = hu.get(x.u)
        hb, hc, hv = set(), set(), set()
        if i is not None:
            sl = slice(H["indptr"][i], H["indptr"][i + 1])
            ps = names[H["prod"][sl]]
            hb, hc, hv = set(ps[H["buys"][sl] > 0]), set(ps[H["carts"][sl] > 0]), set(ps)
        ct, cp = carts.get(x.u, empty)
        vt, vp = views.get(x.u, empty)
        bt, bp = buys.get(x.u, empty)
        tc, tv, tb = set(cp[ct < x.t]), set(vp[vt < x.t]), set(bp[bt < x.t])
        tc_recent = set(cp[(ct < x.t) & (ct > x.t - 3600)])
        for k, p in enumerate(x.shown):
            w = 1 / np.log2(k + 2)
            hist = ("hist bought" if p in hb else "hist carted, not bought" if p in hc else "hist viewed only" if p in hv else "hist never")
            today = ("bought today" if p in tb else "carted today <1 h" if p in tc_recent else "carted today >1 h" if p in tc
                     else "viewed today" if p in tv else "not touched today")
            for key in (hist, today, f"{hist} | {today}", "all"):
                a = acc[key]
                a[0] += w
                a[1] += x.clicked == p
                a[2] += x.purchased == p
    print("| class | impressions (sum w) | clicks | buys | click % per w | buy % per w |\n|---|---|---|---|---|---|")
    for key, (w, c, b) in sorted(acc.items(), key=lambda kv: -kv[1][0]):
        if w < 150:
            continue
        print(f"| {key} | {w:,.0f} | {c} | {b} | {100 * c / w:.2f} | {100 * b / w:.3f} +- {100 * np.sqrt(b) / w:.3f} |")


if __name__ == "__main__":
    main()
