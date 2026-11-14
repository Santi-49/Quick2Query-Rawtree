"""H-home-who questions 1, 4, 5, 6: who the home-page shoppers are, slice by slice. Reads data/home/ (eda/home/pull.py).

    uv run eda/home/who.py
"""
import json

import numpy as np
import pandas as pd

from q2q import rt

D = rt.ROOT / "data" / "home"
SOUTH = {"Andalucía", "Canarias", "Murcia"}
CURRENT = {"agate-h", "shale-h"}  # cold2, ranker2 on the home route


def load():
    r = pd.read_parquet(D / "reqs.parquet").rename(columns={"r.rid": "rid", "r.u": "u"})
    r["home"] = r.nrv == 0
    r["buy"] = r.purchased.fillna("") != ""
    r["clk"] = r.clicked.fillna("") != ""
    r["team"] = r.served == "team"
    r["shopper"] = np.where(r.h_ev > 0, "1 history", np.where(r.ev_before > 0, "2 today only", "3 unknown"))
    r["seg"] = np.where((r.dev == "android") & r.reg.isin(SOUTH), "android-south", "other")
    r["hour"] = pd.to_datetime(r.t, unit="s").dt.hour
    gap = (r.t - r.last_t).where(r.ev_before > 0)
    r["gap"] = pd.cut(gap, [-1, 600, 1800, 7200, 1e9], labels=["<10 min", "10-30 min", "30 min-2 h", ">2 h"]).astype(str).replace("nan", "no event today")
    r["after_buy"] = np.where((r.last_buy_t > 0) & (r.t - r.last_buy_t < 1800), "organic buy <30 min before", "no")
    r = r.sort_values("t")
    r["req_no"] = r.groupby("u").cumcount() + 1
    r["prev_home"] = r.groupby("u").home.shift(1)
    r["prev_buy"] = r.groupby("u").buy.shift(1).fillna(False)
    r["prev_dt"] = r.t - r.groupby("u").t.shift(1)
    return r


def md(df):
    cols = list(df.columns)
    return "\n".join(["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)] +
                     ["| " + " | ".join(str(v) for v in row) + " |" for row in df.itertuples(index=False)])


def rate(g, col):
    n, k = len(g), g[col].sum()
    p = k / n if n else 0
    return f"{100 * p:.2f} +- {100 * np.sqrt(p * (1 - p) / n) if n else 0:.2f} ({k})"


def table(df, by, cols=("buy", "clk"), min_n=200):
    rows = []
    for key, g in df.groupby(by, observed=True):
        if len(g) < min_n:
            continue
        rows.append({"slice": key, "n": len(g), "share": f"{100 * len(g) / len(df):.1f}%", **{c: rate(g, c) for c in cols}})
    return md(pd.DataFrame(rows))


def main():
    r = load()
    end = r.t.max()
    h = r[r.home & r.team]
    print(f"home requests served by us: {len(h):,}; conv {rate(h, 'buy')}, click {rate(h, 'clk')}; current arms {rate(h[h.mv.isin(CURRENT)], 'buy')}")
    for by in ["shopper", "new", "seg", "dev", "reg", "hour", "gap", "after_buy"]:
        print(f"\n### home by {by}\n" + table(h, by))
    h2 = h.assign(prevkind=np.where(h.req_no == 1, "first request today", np.where(h.prev_home == True, "after a home request", "after a request with views")))  # noqa: E712
    print("\n### home by previous request\n" + table(h2, "prevkind"))
    h2 = h2.assign(prevbuy=np.where(h2.prev_buy, "previous request bought from our list", "no"))
    print("\n### home after a list purchase\n" + table(h2, "prevbuy", min_n=20))
    print("\n### home by history purchases\n" + table(h.assign(hb=pd.cut(h.h_buys, [-1, 0, 5, 15, 40, 1e6])), "hb"))
    print("\n### home by history carts\n" + table(h.assign(hc=pd.cut(h.h_carts, [-1, 0, 10, 30, 80, 1e6])), "hc"))
    print("\n### home by organic purchases earlier today\n" + table(h.assign(bb=pd.cut(h.buys_before, [-1, 0, 1, 3, 1e6])), "bb"))
    print("\n### home by carts earlier today\n" + table(h.assign(cb=pd.cut(h.carts_before, [-1, 0, 2, 5, 1e6])), "cb"))
    hc = h[h.t < end - 1800]
    print("\n### home by organic purchase in the 30 min after (shop.events)\n" + table(hc.assign(o=hc.buys_30 > 0), "o"))

    # Q4: organic buying after a request, home vs requests with views (all requests, complete 30-min window)
    a = r[r.t < end - 1800].assign(o30=lambda x: x.buys_30 > 0, o10=lambda x: x.buys_10 > 0, v30=lambda x: x.views_30 > 0)
    print("\n### Q4 organic activity after the request, home vs with views\n" + table(a.assign(k=np.where(a.home, "home", "with views")), "k", ("o10", "o30", "v30", "buy")))
    print("\n### Q4 by shopper class\n" + table(a.assign(k=a.home.map({True: "home ", False: "views "}) + a.shopper), "k", ("o30", "buy")))

    # Q5: after a click on a home list, the shopper's next request and its conversion
    r["next_home"] = r.groupby("u").home.shift(-1)
    r["next_buy"] = r.groupby("u").buy.shift(-1)
    r["next_dt"] = r.groupby("u").t.shift(-1) - r.t
    hh = r[r.home & r.team & (r.t < end - 1800)].copy()
    hh["k"] = np.where(hh.buy, "1 bought", np.where(hh.clk, "2 clicked, no buy", "3 no click"))
    rows = []
    for k, g in hh.groupby("k"):
        nx = g[g.next_dt < 1800]
        nb = nx.next_buy.astype(float)
        rows.append({"home outcome": k, "n": len(g), "next request <30 min": f"{100 * len(nx) / len(g):.1f}%",
                     "next is home": f"{100 * nx.next_home.astype(float).mean():.1f}%",
                     "next converts": f"{100 * nb.mean():.2f} +- {100 * nb.std() / np.sqrt(max(len(nb), 1)):.2f} ({int(nb.sum())})",
                     "organic buy 30 min": f"{100 * (g.buys_30 > 0).mean():.1f}%",
                     "organic views 30 min": f"{g.views_30.mean():.2f}"})
    print("\n### Q5 what follows a home list, by its outcome\n" + md(pd.DataFrame(rows)))
    # does a clicked product show up in the next request's recent views?
    print(f"\n(next request within 30 min after a home click: {int(((hh.clk) & (hh.next_dt < 1800)).sum())} of {int(hh.clk.sum())} clicks)")

    # Q6: lists that converted against those that did not (current arms, home)
    cat = {p["product_id"]: p for p in json.load(open(rt.ROOT / "data" / "catalog.json"))}
    hist = dict(np.load(rt.ROOT / "data" / "user_history.npz"))  # NpzFile decompresses on every access
    users = {u: i for i, u in enumerate(hist["users"])}
    prods = hist["products"]

    def hist_set(u):
        i = users.get(u)
        if i is None:
            return set(), set()
        sl = slice(hist["indptr"][i], hist["indptr"][i + 1])
        ps = prods[hist["prod"][sl]]
        return set(ps[hist["carts"][sl] > 0]) - set(ps[hist["buys"][sl] > 0]), set(ps)

    rows = []
    for _, x in h[h.shown.map(len) == 10].iterrows():
        items = [p for p in x.shown if p in cat]
        if not items:
            continue
        carts, touched = hist_set(x.u)
        rows.append({"buy": x.buy, "clk": x.clk, "cur": x.mv in CURRENT, "known": x.h_ev > 0,
                     "ncat": len({cat[p]["category"] for p in items}), "nsub": len({cat[p]["subcategory"] for p in items}),
                     "price": np.mean([cat[p]["price_eur"] for p in items]), "slot1_price": cat[items[0]]["price_eur"],
                     "hist_share": np.mean([p in touched for p in items]), "cart_share": np.mean([p in carts for p in items])})
    L = pd.DataFrame(rows)
    out = []
    for name, g in [("all home lists, bought", L[L.buy]), ("all home lists, not bought", L[~L.buy]),
                    ("current arms, bought", L[L.cur & L.buy]), ("current arms, not bought", L[L.cur & ~L.buy]),
                    ("known shoppers, bought", L[L.known & L.buy]), ("known shoppers, not bought", L[L.known & ~L.buy])]:
        out.append({"lists": name, "n": len(g), **{c: f"{g[c].mean():.2f} +- {g[c].std() / np.sqrt(len(g)):.2f}" for c in ["ncat", "nsub", "price", "hist_share", "cart_share"]}})
    print("\n### Q6 lists that converted vs not (home, our lists)\n" + md(pd.DataFrame(out)))
    for c, bins in [("ncat", [0, 1, 2, 3, 4, 6, 10]), ("price", [0, 15, 25, 40, 70, 1e4]), ("cart_share", [-0.01, 0, 0.1, 0.3, 1.01])]:
        print(f"\n### Q6 conversion by {c}\n" + table(L.assign(b=pd.cut(L[c], bins)), "b", min_n=150))


if __name__ == "__main__":
    pd.set_option("display.width", 200)
    main()
