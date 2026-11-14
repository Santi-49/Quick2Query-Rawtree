"""Hidden shopper segments: NMF on each shopper's history view shares over category, brand, phrase and price band.

    uv run python eda/ml/segments.py

Shoppers: the returning live shoppers (history < 14 Nov 07:00). Components are described by their top loadings and
their device x region mix. Then: does membership (or the component affinity to the shown product) predict live
clicks beyond category share and device x region? LightGBM on the gbm.py time split, three feature sets.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import NMF

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import ML, ts, products  # noqa: E402
from gbm import auc, fit, split  # noqa: E402
from pulls import END  # noqa: E402
from q2q.state import FEATURES as PHRASES  # noqa: E402

K = 8


def main():
    cat = pd.read_parquet(ML / "catalog.parquet")
    P, _ = products(cat, pd.read_parquet(ML / "products_l.parquet"), pd.read_parquet(ML / "carousel_l.parquet"), ts(END))
    up = pd.read_parquet(ML / "up_l.parquet", columns=["u", "p", "v"])
    code = pd.Series(np.arange(len(P)), index=P.p)
    up = up.assign(pc=up.p.map(code)).dropna(subset=["pc"])
    pc = up.pc.astype(int).to_numpy()
    users, ui = np.unique(up.u, return_inverse=True)
    blocks, names = [], []
    for key, labels in [("cat_i", pd.factorize(cat.cat)[1]), ("brand_i", pd.factorize(cat.brand)[1]), ("ph1", PHRASES), ("band", ["<p20", "p20-40", "p40-60", "p60-80", ">p80"])]:
        cols = [P[key].to_numpy()[pc]] + ([P.ph2.to_numpy()[pc]] if key == "ph1" else [])
        M = np.zeros((len(users), len(labels)), dtype="float32")
        for c in cols:
            np.add.at(M, (ui, c), up.v.to_numpy())
        blocks.append(M / np.maximum(M.sum(1, keepdims=True), 1))
        names += [f"{key[:3]}:{x}" for x in labels]
    S = np.concatenate(blocks, 1)
    keep = up.groupby(ui).v.sum().to_numpy() >= 10
    nmf = NMF(K, init="nndsvda", max_iter=400, random_state=0)
    W = np.zeros((len(users), K), dtype="float32")
    W[keep] = nmf.fit_transform(S[keep])
    H = nmf.components_
    cluster = np.where(keep, W.argmax(1), -1)
    T = pd.read_parquet(ML / "table_live.parquet")
    uix = pd.Series(np.arange(len(users)), index=users)
    row = T.u.map(uix)
    T["cluster"] = np.where(row.notna(), cluster[row.fillna(0).astype(int)], -1)
    # affinity of the shopper's components to the shown product's category, brand, phrases and band
    off = np.cumsum([0] + [b.shape[1] for b in blocks])
    cols = [off[0] + T.p_cat, off[1] + T.p_brand, off[2] + T.p_ph1, off[2] + T.p_ph2, off[3] + T.p_band.astype(int)]
    Wr = np.where(row.notna().to_numpy()[:, None], W[row.fillna(0).astype(int)], np.nan)
    for i, c in enumerate(["aff_cat", "aff_brand", "aff_ph1", "aff_ph2", "aff_band"]):
        T[c] = (Wr * H[:, cols[i].to_numpy().clip(0)].T).sum(1)
    T["aff_total"] = T[["aff_cat", "aff_brand", "aff_ph1", "aff_ph2", "aff_band"]].sum(1)
    dev = T.drop_duplicates("u").set_index("u")[["device", "region", "seg_south"]]

    print(f"shoppers {len(users):,}, clustered (>= 10 history views) {keep.sum():,}; NMF reconstruction error {nmf.reconstruction_err_:.1f}\n")
    for k in range(K):
        top = np.argsort(-H[k])
        u_k = users[cluster == k]
        dk = dev.reindex(u_k).dropna()
        lv = T[T.cluster == k]
        print(f"component {k}: {len(u_k):,} shoppers; top loadings: " + ", ".join(f"{names[j]} {H[k, j]:.2f}" for j in top[:8]))
        print(f"   in live: {len(dk):,} shoppers, android-south {100 * dk.seg_south.mean():.0f}%, device mix {dk.device.value_counts(normalize=True).round(2).to_dict()}, "
              f"impressions {len(lv):,}, clicks {lv.click.sum()}, buys {lv.buy.sum()}")
    # does it add anything? known shoppers only
    K_ = T[T.cluster >= 0].reset_index(drop=True)
    parts = split(K_)
    base = ["slot", "page", "device", "region", "p_cat", "x_cat_share", "seg_south"]
    sets = {"cat share + device x region": base, "+ cluster id": base + ["cluster"], "+ component affinities": base + ["aff_cat", "aff_brand", "aff_ph1", "aff_ph2", "aff_band", "aff_total"],
            "+ explicit x_ shares (brand, sub, phrase, band)": base + ["x_brand_share", "x_sub_share", "x_ph_share", "x_band_share"],
            "explicit shares + affinities": base + ["x_brand_share", "x_sub_share", "x_ph_share", "x_band_share", "aff_brand", "aff_ph1", "aff_ph2", "aff_band", "aff_total"]}
    print(f"\nknown live shoppers: {len(K_):,} impressions, clicks {K_.click.sum()}, buys {K_.buy.sum()}; held-out AUC (newest 20%):")
    for label in ["click", "buy"]:
        for name, cols_ in sets.items():
            K_["cluster"] = K_.cluster.astype("int32")
            m = fit(K_, cols_, label, parts)
            p = m.predict(K_.loc[parts[2], cols_], num_iteration=m.best_iteration)
            print(f"  {label:5s} {name:50s} {auc(K_.loc[parts[2], label].to_numpy(), p):.4f} (trees {m.best_iteration})")
    print("\nclick % per weighted impression by component x shown category (known shoppers, cells with >= 15 clicks):")
    K_["w"] = 1 / np.log2(K_.slot + 1)
    g = K_.groupby(["cluster", "p_cat"]).agg(w=("w", "sum"), clicks=("click", "sum"), buys=("buy", "sum"))
    g["click_pw"] = 100 * g.clicks / g.w
    g = g.join(K_.groupby("p_cat").apply(lambda x: 100 * x.click.sum() / x.w.sum(), include_groups=False).rename("cat_avg"), on="p_cat")
    g["lift"] = g.click_pw / g.cat_avg
    catn = pd.factorize(cat.cat)[1]
    g = g[g.clicks >= 15].reset_index()
    g["p_cat"] = [catn[i] for i in g.p_cat]
    print(g.round(2).sort_values("lift", ascending=False).to_string(index=False))


if __name__ == "__main__":
    main()
