"""Wide impression table for the ML pattern study: one row per shown product, ~170 features.

    uv run python eda/ml/build.py            # uses cached pulls (data/ml/*.parquet)
    uv run python eda/ml/build.py refresh    # re-pulls the live tables first

Writes data/ml/table_live.parquet and data/ml/table_hist.parquet. Feature groups (prefix): slot/context, s_ session,
p_ product, g_ attribute group aggregates, u_ shopper, x_ shopper x product attributes, l_ live store state.
The 21 ranker features keep their names from src/q2q/strategies/ranker.py (BASE).
"""
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pulls import CUT_H, END, ML, pull_all  # noqa: E402
from q2q.state import FEATURES as PHRASES, Product, State, appeal, new_appeal, segment_from  # noqa: E402

BASE = ["slot", "appeal", "log_views", "log_buys", "price", "is_new_product", "is_last_view", "in_views", "views_ago", "same_sub_last", "same_cat_last",
        "same_sub_any", "same_cat_any", "n_views", "viewed_before", "cat_share", "known_shopper", "segment", "page", "device", "new_shopper"]
CATEG = ["page", "device", "region", "p_cat", "p_sub", "p_brand", "p_ph1", "p_ph2", "s_last_cat"]
KEYS = ["cat", "sub", "brand", "band"]
ts = lambda s: datetime.fromisoformat(s).replace(tzinfo=timezone.utc).timestamp()  # noqa: E731


def products(cat, ps, car, cut):
    """Product table indexed like `cat` (row = product code)."""
    P = pd.DataFrame({"p": cat.p, "cat": cat.cat, "sub": cat["sub"], "brand": cat.brand, "price": cat.price, "is_new": cat.is_new})
    flags = np.array([[f in d for f in PHRASES] for d in cat.descr], dtype=bool)
    order = np.argsort(~flags, axis=1, kind="stable")[:, :2]
    P["ph1"], P["ph2"] = order[:, 0], order[:, 1]
    for i, f in enumerate(PHRASES):
        P["p_ph_" + f.split()[0] + "_" + f.split()[-1]] = flags[:, i]
    P = P.merge(ps, on="p", how="left").merge(car, on="p", how="left").fillna({c: 0 for c in ["v", "c", "b", "viewers", "v7", "b7", "imp", "w", "clk", "buy"]})
    P["age_days"] = (cut - cat.created.to_numpy()) / 86400
    P["band"] = np.searchsorted(np.quantile(P.price, [0.2, 0.4, 0.6, 0.8]), P.price)
    P["lp"] = np.log(P.price)
    st = State()
    objs = {r.p: Product(r.p, r.cat, r.sub, r.brand, r.price, tuple(f for f in PHRASES if f in d), bool(r.is_new), int(r.v), int(r.b), 0.0)
            for r, d in zip(P.itertuples(), cat.descr)}
    st._fit(objs)
    P["appeal"] = [new_appeal(*st._predict(o)) if o.views == 0 else appeal(o.views, o.buys, st._predict(o)[1]) for o in objs.values()]
    P["attr_bpv"] = [np.exp(st._predict(o)[1]) for o in objs.values()]
    P["attr_views"] = [np.exp(st._predict(o)[0]) for o in objs.values()]
    f = {"log_views": np.log1p(P.v), "log_buys": np.log1p(P.b), "is_new_product": P.is_new, "appeal": P.appeal, "p_carts": np.log1p(P.c),
         "p_bpv": (P.b + 1) / (P.v + 50), "p_cpv": (P.c + 1) / (P.v + 20), "p_bpc": (P.b + 1) / (P.c + 2), "p_viewers": np.log1p(P.viewers),
         "p_views_per_viewer": P.v / P.viewers.clip(lower=1), "p_trend7": (P.v7 + 5) / 7 / ((P.v - P.v7 + 5) / 53), "p_buytrend7": (P.b7 + 1) / 7 / ((P.b - P.b7 + 1) / 53),
         "p_age_days": P.age_days, "p_attr_bpv": P.attr_bpv, "p_attr_views": np.log(P.attr_views), "p_resid_bpv": np.log((P.b + 1) / (P.v + 50)) - np.log(P.attr_bpv),
         "p_car_imp": np.log1p(P.imp), "p_car_ctr": (P.clk + 0.5) / (P.w + 50), "p_car_cvr": (P.buy + 0.2) / (P.w + 50), "p_car_bpc": (P.buy + 1) / (P.clk + 3),
         "p_band": P.band}
    for g in ["sub", "brand", "cat"]:
        f[f"p_price_pct_{g}"] = P.groupby(g).price.rank(pct=True)
        f[f"p_price_z_{g}"] = P.lp - P.groupby(g).lp.transform("mean")
        agg = P.groupby(g)[["v", "c", "b"]].transform("sum")
        f[f"g_{g}_bpv"], f[f"g_{g}_cpv"] = (agg.b + 1) / (agg.v + 50), (agg.c + 1) / (agg.v + 50)
        f[f"g_{g}_views_pp"] = np.log1p(agg.v / P.groupby(g).p.transform("count"))
        f[f"g_{g}_nprod"] = P.groupby(g).p.transform("count")
    f["g_brand_sub_nprod"] = P.groupby(["brand", "sub"]).p.transform("count")
    for c in ["cat", "sub", "brand"]:
        P[c + "_i"] = pd.factorize(P[c])[0]
    F = pd.DataFrame(f).astype("float32")
    F[[c for c in P if c.startswith("p_ph_")]] = P[[c for c in P if c.startswith("p_ph_")]].astype("float32")
    return P, F


def shoppers(up, users, P):
    """Shopper and shopper x attribute aggregates from the user-product table."""
    code = pd.Series(np.arange(len(P)), index=P.p)
    up = up.assign(pc=up.p.map(code)).dropna(subset=["pc"])
    pc = up.pc.astype(int).to_numpy()
    for k in KEYS:
        up[k] = P[k + "_i" if k != "band" else "band"].to_numpy()[pc]
    up["pct"] = P.groupby("sub").price.rank(pct=True).to_numpy()[pc]
    up["lp"] = P.lp.to_numpy()[pc]
    g = up.groupby("u")
    U = pd.DataFrame({"u_views": g.v.sum(), "u_carts": g.c.sum(), "u_buys": g.b.sum(), "u_nprod": g.size(), "u_nbought": (up.b > 0).groupby(up.u).sum(),
                      "u_last_view": g.lv.max(), "u_price_pct": (up.pct * up.v).groupby(up.u).sum() / g.v.sum().clip(lower=1),
                      "u_lp_mean": (up.lp * up.v).groupby(up.u).sum() / g.v.sum().clip(lower=1)})
    U["u_cpv"], U["u_bpc"] = (U.u_carts + 1) / (U.u_views + 10), (U.u_buys + 1) / (U.u_carts + 2)
    U["u_repeat"] = (U.u_buys - U.u_nbought) / U.u_buys.clip(lower=1)
    X = {}
    for k in KEYS:
        a = up.groupby(["u", k]).agg(v=("v", "sum"), c=("c", "sum"), b=("b", "sum"), lv=("lv", "max"))
        a["share"] = a.v / a.groupby(level=0).v.transform("sum").clip(lower=1)
        a["rank"] = a.groupby(level=0).v.rank(ascending=False, method="min")
        if k == "cat":
            a["pct"] = (up.pct * up.v).groupby([up.u, up.cat]).sum() / a.v.clip(lower=1)
        if k != "band":
            s = a.share[a.share > 0]
            U[f"u_ent_{k}"] = -(s * np.log(s)).groupby(level=0).sum()
            U[f"u_n_{k}"] = s.groupby(level=0).size()
            U[f"u_top_{k}_share"] = s.groupby(level=0).max()
        X[k] = a
    ph = pd.concat([up[["u", "v", "b"]].assign(ph=P.ph1.to_numpy()[pc]), up[["u", "v", "b"]].assign(ph=P.ph2.to_numpy()[pc])])
    a = ph.groupby(["u", "ph"]).agg(v=("v", "sum"), b=("b", "sum"))
    a["share"] = a.v / U.u_views.reindex(a.index.get_level_values(0)).clip(lower=1).to_numpy()
    X["ph"] = a
    users = users.drop_duplicates("u").set_index("u")
    for c in ["ns", "sl_mean", "sl_max", "sl_sd", "sdur_mean", "nd", "hour_mean", "hour_sd", "weekend", "sess_buy_rate", "sess_cart_rate", "last", "first"]:
        U["u_" + c] = users[c].reindex(U.index)
    return U, X, up.set_index(["u", "pc"])[["v", "c", "b", "lv", "lb"]]


def take(keys: pd.DataFrame, table: pd.DataFrame) -> pd.DataFrame:
    """Left-join `table` (indexed by the columns of keys) onto keys, aligned to keys' rows."""
    return table.reindex(pd.MultiIndex.from_frame(keys) if keys.shape[1] > 1 else keys.iloc[:, 0]).reset_index(drop=True)


def window(counts: pd.DataFrame, rows: np.ndarray, t: np.ndarray, n: int):
    """Views per row id in the last 15 and 120 minutes of completed 5-minute buckets before t (live only)."""
    b0, b1 = int(counts.bk.min()), int(counts.bk.max()) + 2
    M = np.zeros((n, b1 - b0 + 1))
    np.add.at(M, (counts.r.to_numpy(), counts.bk.to_numpy().astype(int) - b0), counts.n.to_numpy())
    C = np.concatenate([np.zeros((n, 1)), M.cumsum(1)], axis=1)
    tot = C.sum(0)
    rb = np.clip((t // 300).astype(int) - b0, 0, b1 - b0)
    lo3, lo24 = np.clip(rb - 3, 0, None), np.clip(rb - 24, 0, None)
    return C[rows, rb] - C[rows, lo3], C[rows, rb] - C[rows, lo24], tot[rb] - tot[lo3], tot[rb] - tot[lo24]


def table(imp, P, F, U, X, UP, cov, d, live):
    imp = imp.reset_index(drop=True).assign(ri=lambda x: np.arange(len(x)))
    code = pd.Series(np.arange(len(P)), index=P.p)
    E = imp.drop(columns=["vp", "vt"]).explode("shown")
    E["slot"] = E.groupby("ri").cumcount() + 1
    E["pc"] = E.shown.map(code)
    E = E.dropna(subset=["pc"]).reset_index(drop=True)
    pc, t = E.pc.astype(int).to_numpy(), E.t.to_numpy(dtype=float)
    o = {"slot": E.slot, "inv_log_slot": 1 / np.log2(E.slot + 1), "page": E.page.map({"product": 0, "category": 1, "home": 2}).fillna(-1),
         "device": E.dev.map({"android": 0, "ios": 1, "web": 2}).fillna(-1),
         "region": E.reg.map({r: i for i, r in enumerate(sorted(d["segment"].region.unique()))}).fillna(-1),
         "known_shopper": E.u.isin(U.index), "hour": (t // 3600) % 24, "dow": ((t // 86400) + 3) % 7}
    o["new_shopper"] = E.new.astype(bool) if live else ~o["known_shopper"]
    o["seg_south"] = (E.dev == "android") & (E.reg.str.startswith("Andaluc") | E.reg.isin(["Canarias", "Murcia"]))
    seg = pd.DataFrame([(dv, rg, c, v) for (dv, rg), m in segment_from(d["segment"].to_dict("records")).items() for c, v in m.items()],
                       columns=["a", "b", "c", "lift"]).set_index(["a", "b", "c"])
    o["segment"] = take(pd.DataFrame({"a": E.dev, "b": E.reg, "c": P.cat.to_numpy()[pc]}), seg).lift.fillna(1.0)
    for c in F:
        o[c] = F[c].to_numpy()[pc]
    o["price"] = P.price.to_numpy()[pc]
    for c, src in [("p_cat", "cat_i"), ("p_sub", "sub_i"), ("p_brand", "brand_i"), ("p_ph1", "ph1"), ("p_ph2", "ph2")]:
        o[c] = P[src].to_numpy()[pc]
    # session: the request's recent views against the shown product
    rv = imp[["ri", "t", "vp", "vt"]].explode(["vp", "vt"]).dropna(subset=["vp"])
    rv["vt"] = rv.vt.astype(float)
    rv["j"], rv["vc"] = rv.groupby("ri").cumcount(), rv.vp.map(code).fillna(-1).astype(int)
    rv["n"] = rv.groupby("ri").j.transform("size")
    A = {k: np.append(P[k + "_i" if k != "band" else "band"].to_numpy(), -9) for k in KEYS}
    A |= {"ph1": np.append(P.ph1.to_numpy(), -9), "ph2": np.append(P.ph2.to_numpy(), -9), "lp": np.append(P.lp.to_numpy(), np.nan)}
    R = rv.groupby("ri").agg(n=("n", "first"), t0=("vt", "min"), t1=("vt", "max"), last=("vc", "last"))
    R["n_subs"] = rv.assign(s=A["sub"][rv.vc]).groupby("ri").s.nunique()
    R["n_cats"] = rv.assign(s=A["cat"][rv.vc]).groupby("ri").s.nunique()
    R["lp_mean"] = rv.assign(s=A["lp"][rv.vc]).groupby("ri").s.mean()
    R = R.reindex(E.ri.to_numpy()).reset_index(drop=True)
    last = R["last"].fillna(-1).astype(int).to_numpy()
    o["n_views"] = R.n.fillna(0)
    o["s_span"], o["s_age_last"] = R.t1 - R.t0, t - R.t1
    o["s_n_subs"], o["s_n_cats"], o["s_one_sub"] = R.n_subs, R.n_cats, (R.n_subs == 1) & (R.n > 1)
    o["s_price_rel_mean"], o["s_price_rel_last"] = A["lp"][pc] - R.lp_mean, A["lp"][pc] - A["lp"][last]
    o["s_last_is_new"], o["s_last_appeal"] = np.append(P.is_new.to_numpy(), np.nan)[last], np.append(P.appeal.to_numpy(), np.nan)[last]
    o["s_last_cat"], o["s_last_bpv"] = A["cat"][last], np.append(F.p_bpv.to_numpy(), np.nan)[last]
    M = E[["ri"]].assign(ei=np.arange(len(E)), pc=pc).merge(rv[["ri", "j", "vc", "n"]], on="ri")
    mp, mv = M.pc.to_numpy(), M.vc.to_numpy()
    key, cn = cov.key.to_numpy(), cov.n.to_numpy()

    def co(a, b):
        i = np.clip(np.searchsorted(key, a * 10000 + b), 0, len(key) - 1)
        return np.where((key[i] == a * 10000 + b) & (a >= 0), cn[i], 0)
    ph = sum((A[f][mp] == A[g][mv]).astype(int) for f in ["ph1", "ph2"] for g in ["ph1", "ph2"])
    M = M.assign(same_p=mp == mv, ph=ph, cov=co(mv, mp), lastv=M.j == M.n - 1, **{k: A[k][mp] == A[k][mv] for k in KEYS})
    M["jp"] = np.where(M.same_p, M.j, -1)
    g = M.groupby("ei")
    cols = ["same_p", "ph", "cov", *KEYS]
    M[cols] = M[cols].astype(int)
    S = g[cols].sum().reindex(range(len(E)), fill_value=0)
    L = M[M.lastv].set_index("ei")[cols].reindex(range(len(E)), fill_value=0)
    o["in_views"], o["s_n_same_p"], o["is_last_view"] = S.same_p > 0, S.same_p, L.same_p
    o["views_ago"] = np.where(S.same_p > 0, o["n_views"] - g.jp.max().reindex(range(len(E)), fill_value=-1), 0)
    o["same_sub_last"], o["same_cat_last"], o["s_same_brand_last"], o["s_same_band_last"], o["s_ph_overlap_last"] = L["sub"], L["cat"], L["brand"], L["band"], L.ph
    o["same_sub_any"], o["same_cat_any"] = S["sub"] > 0, S["cat"] > 0
    for k in KEYS:
        o[f"s_n_same_{k}"] = S[k]
    o["s_ph_overlap_sum"], o["s_coview_any"], o["s_coview_last"], o["s_coview_last_rev"] = S.ph, S["cov"], L["cov"], co(pc, last)
    outdeg = np.append(cov.assign(a=cov.key // 10000).groupby("a").n.sum().reindex(range(len(P)), fill_value=0).to_numpy(), 0)
    o["s_coview_last_share"] = L["cov"].to_numpy() / np.maximum(outdeg[last], 1)
    # shopper, shopper x product, shopper x attributes
    Ut = take(E[["u"]], U)
    known = o["known_shopper"].to_numpy()
    for c in U.columns.drop(["u_last", "u_first", "u_last_view"]):
        o[c] = Ut[c].to_numpy()
    o["u_days_since"], o["u_tenure"] = (t - Ut.u_last) / 86400, (t - Ut.u_first) / 86400
    o["u_hour_diff"] = np.minimum(abs(o["hour"] - Ut.u_hour_mean), 24 - abs(o["hour"] - Ut.u_hour_mean))
    x = take(pd.DataFrame({"u": E.u, "pc": pc}), UP)
    z = lambda s: np.where(known, s.fillna(0), np.nan)  # noqa: E731 - known shopper who never touched it = 0
    o["viewed_before"] = np.where(x.b.fillna(0) > 0, 0, z(x.v).clip(max=20))
    o["x_p_views"], o["x_p_carts"], o["x_p_buys"], o["x_p_bought"] = z(x.v), z(x.c), z(x.b), z(x.b) > 0
    o["x_p_cart_nobuy"] = (z(x.c) > 0) & (z(x.b) == 0)
    o["x_p_days_view"], o["x_p_days_buy"] = np.where(x.lv > 0, (t - x.lv) / 86400, np.nan), np.where(x.lb > 0, (t - x.lb) / 86400, np.nan)
    for k in KEYS:
        a = take(pd.DataFrame({"u": E.u, k: A[k][pc]}), X[k])
        for c in ["v", "c", "b", "share"]:
            o[f"x_{k}_{c}"] = z(a[c])
        o[f"x_{k}_rank"], o[f"x_{k}_days"] = a["rank"], np.where(a.lv > 0, (t - a.lv) / 86400, np.nan)
        if k == "cat":
            o["cat_share"], o["x_cat_pct_diff"] = o["x_cat_share"], o["p_price_pct_sub"] - a.pct
    a1, a2 = (take(pd.DataFrame({"u": E.u, "ph": A[f][pc]}), X["ph"]) for f in ["ph1", "ph2"])
    o["x_ph_share"], o["x_ph_buys"] = z(a1.share.fillna(0) + a2.share.fillna(0)), z(a1.b.fillna(0) + a2.b.fillna(0))
    o["x_ph_max_share"] = np.fmax(a1.share, a2.share)
    o["x_price_pct_diff"], o["x_lp_diff"] = o["p_price_pct_sub"] - Ut.u_price_pct, A["lp"][pc] - Ut.u_lp_mean
    if live:  # live store state: price changes, stock changes, view trends of the last 15 / 120 minutes
        upd = d["updates"].assign(t=lambda u: u.t.astype(float)).sort_values("t")
        q = pd.DataFrame({"ei": np.arange(len(E)), "t": t, "p": E.shown, "base": o["price"]}).sort_values("t")
        for ch, name in [(["price_change"], "price"), (["out_of_stock", "back_in_stock"], "stock")]:
            m = pd.merge_asof(q, upd[upd.change.isin(ch)].rename(columns={"t": "tc"}), left_on="t", right_on="tc", by="p").sort_values("ei")
            o[f"l_mins_{name}"] = ((m.t - m.tc) / 60).to_numpy()
            if name == "price":
                o["price"] = m.price.fillna(m.base).to_numpy()
                o["l_price_ratio"] = o["price"] / m.base.to_numpy()
        tr = d["trend"].assign(r=lambda x: x.p.map(code)).dropna(subset=["r"]).astype({"r": int})
        p15, p120, t15, t120 = window(tr, pc, t, len(P))
        s15, s120, _, _ = window(tr.assign(r=P.sub_i.to_numpy()[tr.r]), P.sub_i.to_numpy()[pc], t, int(P.sub_i.max()) + 1)
        base = (t15 + 1) / (t120 / 8 + 1)
        o["l_sub_trend"], o["l_p_trend"] = (s15 + 2) / (s120 / 8 + 2) / base, (p15 + 1) / (p120 / 8 + 1) / base
        o["l_p_views15"], o["l_sub_views15"] = np.log1p(p15), np.log1p(s15)
    T = pd.DataFrame({k: np.asarray(v, dtype="float32") for k, v in o.items()})
    T[CATEG] = T[CATEG].fillna(-1).astype("int32")
    meta = pd.DataFrame({"rid": E.rid, "t": t, "u": E.u, "mv": E.mv.fillna(""), "p": E.shown,
                         "click": (E.shown == E.clicked).astype("int8"), "buy": (E.shown == E.purchased).astype("int8")})
    return pd.concat([meta, T], axis=1)


if __name__ == "__main__":
    start = time.time()
    d = pull_all(refresh="refresh" in sys.argv)
    c = d["coview"].groupby(["a", "b"]).n.sum().reset_index()
    code = pd.Series(np.arange(len(d["catalog"])), index=d["catalog"].p)
    cov = pd.DataFrame({"key": c.a.map(code) * 10000 + c.b.map(code), "n": c.n}).dropna().astype("int64").sort_values("key")
    del c
    for tag, cut, live in (("hist", ts(CUT_H), False), ("live", ts(END), True)):
        s = "l" if live else "h"
        P, F = products(d["catalog"], d["products_" + s], d["carousel_" + s], cut)
        U, X, UP = shoppers(d["up_" + s], d["users_" + s], P)
        T = table(d["imp_" + tag], P, F, U, X, UP, cov, d, live)
        T.to_parquet(ML / f"table_{tag}.parquet")
        print(f"table_{tag}: {len(T):,} rows, {T.shape[1] - 7} features, clicks {T.click.sum():,}, buys {T.buy.sum():,}, {time.time() - start:.0f} s", flush=True)
        del T, U, X, UP
