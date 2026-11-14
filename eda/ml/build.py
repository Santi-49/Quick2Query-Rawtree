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
    users = users.set_index("u")
    for c in ["ns", "sl_mean", "sl_max", "sl_sd", "sdur_mean", "nd", "hour_mean", "hour_sd", "weekend", "sess_buy_rate", "sess_cart_rate", "last", "first"]:
        U["u_" + c] = users[c].reindex(U.index)
    return U, X, up.set_index(["u", "pc"])[["v", "c", "b", "lv", "lb"]]


def take(keys: pd.DataFrame, table: pd.DataFrame) -> pd.DataFrame:
    """Left-join `table` (indexed by the columns of keys) onto keys, aligned to keys' rows."""
    return table.reindex(pd.MultiIndex.from_frame(keys) if keys.shape[1] > 1 else keys.iloc[:, 0]).reset_index(drop=True)
