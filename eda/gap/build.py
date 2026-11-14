"""H-gap table: every impression of our feedback with the shown product's place in the shopper's world at request time.

    uv run python eda/gap/pull.py && uv run python eda/gap/build.py   -> data/gap/imp.parquet, req.parquet, org.parquet

Classes, first match wins: bought (history, organic today or through our lists before the request), rv_only / rv_first /
rv_last / rv_other (recent views), cart_today (organic add_to_cart today before the request, not bought), viewed_today,
hist_cart, hist_view, same_sub, same_cat (as any recent view), fav_cat (top history category), none.
"""
import bisect
import math
from collections import defaultdict

import pandas as pd

from q2q import rt
from q2q.state import State

OUT = rt.ROOT / "data" / "gap"
CLASSES = ["bought", "rv_only", "rv_first", "rv_last", "rv_other", "cart_today", "viewed_today", "hist_cart", "hist_view",
           "same_sub", "same_cat", "fav_cat", "none"]
W = [1 / math.log2(k + 2) for k in range(10)]


def route(views, new):
    return ("new" if new else "ret") + ("_views" if len(views) else "_home")


def main():
    st = State()
    st.load()
    P = st.products
    fb = pd.read_parquet(OUT / "fb.parquet")
    fb = fb[fb.req_ts > 1.7e12].sort_values("req_ts")
    ev = pd.read_parquet(OUT / "ev.parquet").sort_values("ts")
    upd = pd.DataFrame(rt.query("""SELECT toUnixTimestamp64Milli(ts::DateTime64(3, 'UTC')) AS ts, product_id::String AS p, change::String AS c,
                                          price_eur::Float64 AS price FROM shop.catalog_updates ORDER BY ts"""))
    # stock and price timelines
    stock, price = defaultdict(list), defaultdict(list)
    for u in upd.itertuples():
        if u.c in ("out_of_stock", "back_in_stock"):
            stock[u.p].append((u.ts, u.c == "out_of_stock"))
        elif u.c == "price_change":
            price[u.p].append((u.ts, u.price))
    base = st._base_price

    def out_at(p, t):
        s = stock.get(p)
        if not s:
            return False
        i = bisect.bisect_right(s, (t, True)) - 1
        return i >= 0 and s[i][1]

    def price_at(p, t):
        s = price.get(p)
        i = bisect.bisect_right(s, (t, 1e18)) - 1 if s else -1
        return s[i][1] if i >= 0 else base.get(p, float("nan"))

    evg = {u: d for u, d in ev.groupby("user_id")}
    our_buys = defaultdict(list)  # user -> (ts, product) bought through our lists
    for r in fb[fb.purchased != ""].itertuples():
        our_buys[r.user_id].append((r.req_ts, r.purchased))

    imps, reqs, orgs = [], [], []
    hist_cache = {}
    for r in fb.itertuples():
        u, t, views = r.user_id, r.req_ts, list(r.views)
        if u not in hist_cache:
            hist_cache[u] = st.shopper(u, live=False)
        h = hist_cache[u]
        hb = h.bought if h else set()
        hv = h.viewed if h else {}
        hc = h.carted if h else {}
        shares = h.cat_share if h else {}
        fav = max(shares, key=shares.get) if shares else None
        usual = [P[p].price for p in hv if p in P]
        usual = sorted(usual)[len(usual) // 2] if usual else None
        d = evg.get(u)
        tv, tvn, tvp, tc, tcl, tb, n_ev, after = {}, defaultdict(int), {}, {}, {}, set(), 0, []
        if d is not None:
            before = d[d.ts < t]
            n_ev = len(before)
            for e in before.itertuples():
                if e.et == "view":
                    tv[e.product_id] = e.ts
                    tvn[e.product_id] += 1
                    tvp[e.product_id] = e.price
                elif e.et == "add_to_cart":
                    tc.setdefault(e.product_id, e.ts)
                    tcl[e.product_id] = e.ts
                else:
                    tb.add(e.product_id)
            after = d[(d.ts >= t) & (d.ts < t + 600_000) & (d.et == "purchase")].product_id.tolist()
        ob = {p for ts, p in our_buys.get(u, ()) if ts < t}
        bought = hb | tb | ob
        vsub = {P[p].subcategory for p in views if p in P}
        vcat = {P[p].category for p in views if p in P}

        def cls(p):
            if p in bought:
                return "bought"
            if p in views:
                if len(set(views)) == 1:
                    return "rv_only"
                return "rv_first" if p == views[0] else "rv_last" if p == views[-1] else "rv_other"
            if p in tc:
                return "cart_today"
            if p in tv:
                return "viewed_today"
            if p in hc:
                return "hist_cart"
            if p in hv:
                return "hist_view"
            q = P.get(p)
            if q is None:
                return "none"
            if q.subcategory in vsub:
                return "same_sub"
            if q.category in vcat:
                return "same_cat"
            if q.category == fav:
                return "fav_cat"
            return "none"

        rt_ = route(views, r.is_new)
        shown = list(r.shown)
        for k, p in enumerate(shown[:10]):
            q = P.get(p)
            pr = price_at(p, t)
            imps.append((r.request_id, rt_, r.model_version, r.served_by, k + 1, W[k], p, cls(p), int(r.purchased == p), int(r.clicked == p),
                         n_ev, tvn.get(p, 0), (t - tcl[p]) / 60000 if p in tcl else None, (t - tv[p]) / 60000 if p in tv else None,
                         pr / usual if usual and pr == pr else None, pr / tvp[p] if p in tvp and tvp[p] else None,
                         hc.get(p, 0), (pr / base[p]) if p in base and base[p] else None, len(views), len(set(views)),
                         views.index(p) if p in views else -1, q.category if q else "", (t - r.view_ts[-1]) / 1000 if len(views) else None))
        # what the shopper had (available) per class, and best slot we gave it
        have = defaultdict(set)
        for p in set(views) | set(tc) | set(tv) | set(hc):
            if p in P and not out_at(p, t) and p not in st._inactive:
                have[cls(p)].add(p)
        pos = {p: k + 1 for k, p in enumerate(shown)}
        row = {"request_id": r.request_id, "route": rt_, "mv": r.model_version, "served_by": r.served_by, "bought": int(r.purchased != ""),
               "n_ev": n_ev, "user_id": u, "ts": t}
        for c in ("rv_only", "rv_first", "rv_last", "rv_other", "cart_today", "viewed_today", "hist_cart"):
            row["has_" + c] = len(have[c])
            row["slot_" + c] = min((pos[p] for p in have[c] if p in pos), default=0)
        reqs.append(row)
        if r.purchased == "":
            # lists of 10 per class, at request time
            lists = {"recent_views": list(dict.fromkeys(reversed(views)))[:10],
                     "cart_today": sorted(tc, key=tcl.get, reverse=True)[:10],
                     "viewed_today": sorted(tv, key=tv.get, reverse=True)[:10],
                     "viewed_today_most": sorted(tv, key=lambda p: (tvn[p], tv[p]), reverse=True)[:10],
                     "hist_cart": sorted(hc, key=hc.get, reverse=True)[:10],
                     "shown": shown}
            for p in dict.fromkeys(after):
                orgs.append({"request_id": r.request_id, "route": rt_, "product": p, "cls": cls(p),
                             **{"in_" + k: int(p in v) for k, v in lists.items()},
                             "in_any3": int(p in set(lists["recent_views"]) | set(lists["cart_today"]) | set(lists["viewed_today"]))})
    cols = ["request_id", "route", "mv", "served_by", "slot", "w", "product", "cls", "buy", "click", "n_ev", "today_views", "min_since_cart",
            "min_since_today_view", "price_rel_usual", "price_since_view", "hist_carts", "price_vs_base", "n_views", "n_distinct", "view_pos",
            "category", "sec_since_last_view"]
    pd.DataFrame(imps, columns=cols).to_parquet(OUT / "imp.parquet")
    pd.DataFrame(reqs).to_parquet(OUT / "req.parquet")
    pd.DataFrame(orgs).to_parquet(OUT / "org.parquet")
    print(len(imps), len(reqs), len(orgs))


if __name__ == "__main__":
    main()
