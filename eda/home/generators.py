"""H-home-who questions 2 and 3: what home-page shoppers buy, relative to themselves, and the oracle hit@10 of each
candidate generator used alone. Reads data/home/ (eda/home/pull.py), data/user_history.npz, data/catalog.json.

    uv run eda/home/generators.py

Targets:
  organic  every organic purchase (shop.events) by the shopper in the 30 min after a home request (complete windows only)
  list     the shown product bought from a home list (team or fallback)
For each generator: coverage = share of targets inside its full candidate set; size = mean candidate-set size;
hit10 = share of requests whose top 10 holds a target (organic) / the bought product (list).
"""
import bisect
import json
from collections import defaultdict

import numpy as np
import pandas as pd

from q2q import rt

D = rt.ROOT / "data" / "home"
STEP = 900  # snapshot grid for today's best sellers and prices, seconds


def main():
    r = pd.read_parquet(D / "reqs.parquet").rename(columns={"r.rid": "rid", "r.u": "u"})
    end = r.t.max()
    home = r[(r.nrv == 0)].copy()
    buys = pd.read_parquet(D / "buys.parquet").sort_values("t")
    carts = pd.read_parquet(D / "carts.parquet").sort_values("t")
    views = pd.read_parquet(D / "views.parquet").sort_values("t")
    last_sess = pd.read_parquet(D / "lastsess.parquet")
    last_buy = dict(pd.read_parquet(D / "lastbuy.parquet")[["u", "p"]].values)
    upd = pd.read_parquet(D / "updates.parquet").sort_values("t")

    meta = {p["product_id"]: (p["category"], p["subcategory"], p["brand"], p["price_eur"]) for p in json.load(open(rt.ROOT / "data" / "catalog.json"))}
    for x in upd[upd.change == "new_product"].itertuples():
        meta.setdefault(x.p, (x.category, x.subcategory, x.brand, x.price))
    pid = {p: i for i, p in enumerate(meta)}
    names = np.array(list(meta))
    P = len(pid)
    cat_of = np.array([meta[p][0] for p in names])
    sub_of = np.array([meta[p][1] for p in names])
    brand_of = np.array([meta[p][2] for p in names])

    # history, per user and per product
    H = dict(np.load(rt.ROOT / "data" / "user_history.npz"))  # NpzFile decompresses on every access
    hu = {u: i for i, u in enumerate(H["users"])}
    hp = np.array([pid[p] for p in H["products"]])
    prod_idx = hp[H["prod"]]
    hist_sales = np.bincount(prod_idx, weights=H["buys"], minlength=P)
    alltime = np.argsort(-hist_sales)
    by_sub, by_cat = defaultdict(list), defaultdict(list)
    for i in alltime:
        by_sub[sub_of[i]].append(i)
        by_cat[cat_of[i]].append(i)
    # co-purchase counts from history (user-level co-occurrence of purchases)
    bought_rows = np.repeat(np.arange(len(H["users"])), np.diff(H["indptr"]))[H["buys"] > 0]
    bought_cols = prod_idx[H["buys"] > 0]
    import scipy.sparse as sp
    B = sp.csr_matrix((np.ones(len(bought_rows), dtype=np.float32), (bought_rows, bought_cols)), shape=(len(H["users"]), P))
    C = (B.T @ B).tocsr()

    # today's best sellers: cumulative counts on a grid, overall and by device x region
    t0 = buys.t.min()
    grid = np.arange(t0, end + STEP, STEP)
    bi = buys.p.map(pid).fillna(-1).astype(int).values
    ok = bi >= 0
    slot = np.searchsorted(grid, buys.t.values, side="right")  # purchase counts from grid index `slot` on
    cum = np.zeros((len(grid) + 1, P), np.int32)
    np.add.at(cum, (slot[ok], bi[ok]), 1)
    cum = cum.cumsum(0)
    segs = {s: k for k, s in enumerate(sorted(set(zip(buys.dev, buys.reg))))}
    sk = np.array([segs[s] for s in zip(buys.dev, buys.reg)])
    seg_cum = np.zeros((len(segs), len(grid) + 1, P), np.int16)
    np.add.at(seg_cum, (sk[ok], slot[ok], bi[ok]), 1)
    seg_cum = seg_cum.cumsum(1)

    def gidx(t):
        return np.searchsorted(grid, t, side="right")  # counts of purchases with ts < grid[g-1] <= t

    # prices: a cut is a price below the catalogue price, on the 5-minute grid
    base = np.array([meta[p][3] for p in names])
    pc = upd[upd.change == "price_change"]
    pc_t, pc_p, pc_price = pc.t.values, pc.p.map(pid).values, pc.price.values

    def cuts_at(t):
        k = bisect.bisect_right(pc_t, t)
        cur = {}
        for p, pr in zip(pc_p[:k], pc_price[:k]):
            cur[p] = pr
        return [p for p, pr in cur.items() if pr < base[p] * 0.99]

    cut_cache = {}

    def per_user(df):
        out = defaultdict(lambda: (np.empty(0), np.empty(0, int)))
        for u, g in df.groupby("u"):
            out[u] = (g.t.values, g.p.map(pid).fillna(-1).astype(int).values)
        return out

    U_buys, U_carts, U_views = per_user(buys), per_user(carts), per_user(views)
    ls = defaultdict(list)
    for u, g in last_sess.groupby("u"):
        ls[u] = [pid[p] for p in g.p.value_counts().index if p in pid]

    def top(seq, k=10):
        out, seen = [], set()
        for x in seq:
            if x not in seen and x >= 0:
                seen.add(x)
                out.append(x)
                if len(out) == k:
                    break
        return out

    rows = []
    shown_buy = home.purchased.fillna("") != ""
    for x in home.itertuples():
        complete = x.t < end - 1800
        bt, bp = U_buys[x.u]
        lo, hi = np.searchsorted(bt, x.t), np.searchsorted(bt, x.t + 1800)
        organic = set(bp[lo:hi][bp[lo:hi] >= 0]) if complete else set()
        listbuy = {pid[x.purchased]} if x.purchased and x.purchased in pid else set()
        if not organic and not listbuy:
            continue
        # shopper's history
        i = hu.get(x.u)
        if i is not None:
            sl = slice(H["indptr"][i], H["indptr"][i + 1])
            p_, v_, b_, c_ = prod_idx[sl], H["views"][sl].astype(int), H["buys"][sl].astype(int), H["carts"][sl].astype(int)
        else:
            p_ = v_ = b_ = c_ = np.empty(0, int)
        # today before the request
        ct, cp = U_carts[x.u]
        vt, vp = U_views[x.u]
        today_carts = cp[: np.searchsorted(ct, x.t)][::-1]
        today_views = vp[: np.searchsorted(vt, x.t)][::-1]
        today_bought = set(bp[:lo])
        g = gidx(x.t)
        today_rank = np.argsort(-cum[g])[:50]
        hour_rank = np.argsort(-(cum[g] - cum[max(g - 4, 0)]))[:10]
        s = segs.get((x.dev, x.reg))
        seg_rank = np.argsort(-seg_cum[s, g])[:50] if s is not None else np.empty(0, int)
        if g not in cut_cache:
            cl = cuts_at(x.t)
            cut_cache[g] = sorted(cl, key=lambda p: -hist_sales[p])
        cut = cut_cache[g]
        vshare = defaultdict(float)
        for p, v in zip(p_, v_):
            vshare[cat_of[p]] += v
        top_cat = max(vshare, key=vshare.get) if vshare else None
        sshare, bshare = defaultdict(float), defaultdict(float)
        for p, v in zip(p_, v_):
            sshare[sub_of[p]] += v
            bshare[brand_of[p]] += v
        top_sub = max(sshare, key=sshare.get) if sshare else None
        top_brand = max(bshare, key=bshare.get) if bshare else None
        lb = last_buy.get(x.u)
        co = []
        if lb in pid:
            row = C.getrow(pid[lb])
            order = np.argsort(-row.data)
            co = [row.indices[j] for j in order if row.indices[j] != pid[lb]][:50]
        today_sub = sub_of[today_views[0]] if len(today_views) and today_views[0] >= 0 else None

        o = np.lexsort
        gens = {
            "hist repurchase": [p_[j] for j in o((-v_, -b_)) if b_[j] > 0],
            "hist carts not bought": [p_[j] for j in o((-v_, -c_)) if c_[j] > 0 and b_[j] == 0],
            "hist viewed only": [p_[j] for j in np.argsort(-v_) if c_[j] == 0 and b_[j] == 0],
            "last hist session": ls.get(x.u, []),
            "co-purchase of last hist buy": co,
            "fav subcategory best sellers": by_sub.get(top_sub, []),
            "fav category best sellers": by_cat.get(top_cat, []),
            "all-time best sellers": list(alltime[:50]),
            "today best sellers": list(today_rank),
            "last-hour best sellers": list(hour_rank),
            "segment today best sellers": list(seg_rank),
            "viewed today": top(today_views, 1000),
            "carted today": top(today_carts, 1000),
            "today's last-view subcategory best sellers": by_sub.get(today_sub, []),
            "price cut, best sellers": cut,
        }
        known = "history" if i is not None and len(p_) else ("today only" if x.ev_before > 0 else "unknown")
        for target, tset in (("organic", organic), ("list", listbuy)):
            if not tset:
                continue
            rec = {"target": target, "known": known, "n_t": len(tset),
                   "rebuy_hist": any(b_[np.isin(p_, list(tset))] > 0) if len(p_) else False,
                   "same top cat": any(cat_of[p] == top_cat for p in tset), "same top sub": any(sub_of[p] == top_sub for p in tset),
                   "same top brand": any(brand_of[p] == top_brand for p in tset),
                   "bought earlier today": bool(tset & today_bought)}
            for name, cands in gens.items():
                full = set(cands)
                rec[f"cov|{name}"] = bool(tset & full)
                rec[f"size|{name}"] = len(full)
                rec[f"hit|{name}"] = bool(tset & set(top(cands)))
            rows.append(rec)
    R = pd.DataFrame(rows)
    R.to_parquet(D / "generators.parquet")
    report(R)


def report(R):
    names = [c[4:] for c in R.columns if c.startswith("cov|")]
    for target in ("organic", "list"):
        for known in (None, "history", "today only", "unknown"):
            g = R[R.target == target] if known is None else R[(R.target == target) & (R.known == known)]
            if len(g) < 20:
                continue
            n = len(g)
            print(f"\n### {target} purchases after home requests, shoppers: {known or 'all'} ({n} requests)")
            print("| generator | applies | coverage (full set) | mean size when applies | hit@10 |\n|---|---|---|---|---|")
            for name in names:
                cov, hit, size = g[f"cov|{name}"], g[f"hit|{name}"], g[f"size|{name}"]
                se = lambda s: 100 * np.sqrt(s.mean() * (1 - s.mean()) / n)  # noqa: E731
                print(f"| {name} | {100 * (size > 0).mean():.0f}% | {100 * cov.mean():.1f} +- {se(cov):.1f} | {size[size > 0].mean():.0f} | "
                      f"{100 * hit.mean():.1f} +- {se(hit):.1f} |")
            for c in ("rebuy_hist", "same top cat", "same top sub", "same top brand", "bought earlier today"):
                print(f"- {c}: {100 * g[c].mean():.1f}%")


if __name__ == "__main__":
    main()
