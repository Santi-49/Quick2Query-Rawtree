"""H-drift tests 1 and 2: do purchases per view move between time units more than binomial noise allows?

    uv run python eda/drift/counts.py live [--cached]       # today, 2-hour blocks (and 1-hour)
    uv run python eda/drift/counts.py history [--cached]    # 16 Sep - 13 Nov, days

Counts come from sql/hypotheses/H-drift.sql (product x unit x user half), cached under data/drift/.
Per product i and unit k: expected buys e = v * p_i * g_k (p_i over all units, g_k the global factor of unit k).
  between   chi2 of b against e, summed over products, divided by its degrees of freedom (K-1 per product)
  within    the same unit's two user halves against each other: the noise floor, shopper clustering included
  tau       excess coefficient of variation of the true rate across units: sum((b-e)^2 - var*within) / sum(e^2)
Groups (subcategory, brand, phrase, category): residuals summed over the group's products per unit, same statistics.
Co-movement shows as a group ratio above the product ratio. History also: lag 1-7 autocorrelation of residuals and
the share of the first 3 principal components of the subcategory x day residual matrix, against a day-shuffled null.
"""
import json
import sys

import numpy as np
import pandas as pd

from q2q import rt
from q2q.state import phrases

OUT = rt.ROOT / "data" / "drift"
MIN_BUYS = 30  # products with fewer purchases over the whole period are left out


def pull(which: str, cached: bool) -> pd.DataFrame:
    path = OUT / f"{which}.parquet"
    if cached and path.exists():
        return pd.read_parquet(path)
    text = (rt.ROOT / "sql" / "hypotheses" / "H-drift.sql").read_text(encoding="utf-8")
    sql = [s for s in text.split(";") if f"-- {1 if which == 'live' else 2} {which}" in s][0]
    sql = "\n".join(line for line in sql.splitlines() if not line.startswith("--"))
    parts = [rt.query(f"SELECT * FROM ({sql}) WHERE cityHash64(p) % 4 = {k}", timeout=60) for k in range(4)]
    df = pd.DataFrame([r for part in parts for r in part])
    for c in ("v", "b", "h") + (("c", "hr") if which == "live" else ()):
        df[c] = df[c].astype(int)
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path)
    return df


def stats(df: pd.DataFrame, unit: str, groups: dict) -> dict:
    """Between-unit and within-unit dispersion for products and for each grouping; returns residual matrices too."""
    full = df.groupby(["p", unit], as_index=False)[["v", "b"]].sum()
    tot = full.groupby("p")[["v", "b"]].sum()
    keep = tot.index[(tot["b"] >= MIN_BUYS)]
    full = full[full["p"].isin(keep)]
    units = sorted(full[unit].unique())
    V = full.pivot(index="p", columns=unit, values="v").reindex(columns=units).fillna(0).to_numpy()
    B = full.pivot(index="p", columns=unit, values="b").reindex(columns=units).fillna(0).to_numpy()
    pids = list(full.pivot(index="p", columns=unit, values="v").index)
    halves = df[df["p"].isin(keep)].pivot_table(index="p", columns=[unit, "h"], values=["v", "b"], aggfunc="sum").reindex(pids).fillna(0)
    V0 = np.stack([halves["v"].get((u, 0), pd.Series(0, index=pids)).to_numpy() for u in units], 1)
    B0 = np.stack([halves["b"].get((u, 0), pd.Series(0, index=pids)).to_numpy() for u in units], 1)
    p = B.sum(1) / V.sum(1)
    out = {"units": units, "pids": pids, "products": len(pids), "views": int(V.sum()), "buys": int(B.sum())}
    for label, g in (("no global factor", np.ones(len(units))), ("global factor", None)):
        if g is None:  # g_k = observed / expected per unit, iterated once with p
            g = B.sum(0) / (V * p[:, None]).sum(0)
            p = B.sum(1) / (V * g[None, :]).sum(1)
            out["g"] = g
        E = V * p[:, None] * g[None, :]
        var = V * p[:, None] * (1 - p[:, None])
        R = B - E
        has = V > 0
        dfree = (has.sum(1) - 1).clip(0)
        between = (R ** 2 / np.where(has, var, 1)).sum() / dfree.sum()
        out[label] = between
    # within: half 0 against the unit's pooled rate, variance p(1-p) v0 v1 / v
    V1 = V - V0
    W = B0 - V0 * np.divide(B, V, out=np.zeros_like(B, dtype=float), where=V > 0)
    wvar = p[:, None] * (1 - p[:, None]) * V0 * V1 / np.where(V > 0, V, 1)
    ok = wvar > 0
    within = (W[ok] ** 2 / wvar[ok]).sum() / ok.sum()
    out["within"] = within
    shrink = (dfree / has.sum(1).clip(1))[:, None]  # a fitted rate per product takes one unit's worth of variance
    out["tau"] = np.sqrt(max(0.0, ((R ** 2 - var * within * shrink)[has]).sum() / (E[has] ** 2).sum()))
    out["R"], out["var"], out["E"], out["W"], out["wvar"] = R, var, E, W, wvar
    for name, of in groups.items():  # of: product -> list of group labels
        labels = sorted({x for pid in pids for x in of.get(pid, ())})
        M = np.zeros((len(labels), len(pids)))
        index = {x: j for j, x in enumerate(labels)}
        for i, pid in enumerate(pids):
            for x in of.get(pid, ()):
                M[index[x], i] = 1
        S, SV, SE = M @ R, M @ var, M @ E
        S0, SV0 = M @ W, M @ wvar
        n = M.sum(1)
        big = n >= 3
        hasg = SV > 0
        gb = (S[big] ** 2 / np.where(hasg[big], SV[big], 1)).sum() / ((hasg[big].sum(1) - 1).clip(0)).sum()
        okg = SV0[big] > 0
        gw = (S0[big][okg] ** 2 / SV0[big][okg]).sum() / okg.sum()
        k = hasg[big].sum(1, keepdims=True)
        tau = np.sqrt(max(0.0, (S[big] ** 2 - SV[big] * gw * (k - 1) / k.clip(1))[hasg[big]].sum() / (SE[big][hasg[big]] ** 2).sum()))
        out[f"group {name}"] = (int(big.sum()), float(np.median(n[big])), gb, gw, tau)
        out[f"Z {name}"] = (S[big] / np.sqrt(np.where(hasg[big], SV[big], 1)), [x for x, k in zip(labels, big) if k])
    return out


def autocorr(Z: np.ndarray, lags=range(1, 8)) -> list[float]:
    Z = Z - Z.mean(1, keepdims=True)
    return [float((Z[:, :-L] * Z[:, L:]).sum() / (Z ** 2).sum()) for L in lags]


def pca_share(Z: np.ndarray, k: int = 3) -> float:
    Z = Z - Z.mean(1, keepdims=True)
    s = np.linalg.svd(Z, compute_uv=False) ** 2
    return float(s[:k].sum() / s.sum())


def views_dispersion(df: pd.DataFrame, unit: str, of: dict) -> float:
    """Chi2 / df of subcategory view counts per unit against the subcategory's overall share (trend in views)."""
    df = df.assign(s=df["p"].map(lambda x: of.get(x, ("?",))[0]))
    T = df.pivot_table(index="s", columns=unit, values="v", aggfunc="sum").fillna(0).to_numpy()
    E = T.sum(1, keepdims=True) * T.sum(0, keepdims=True) / T.sum()
    return float(((T - E) ** 2 / E).sum() / ((T.shape[0] - 1) * (T.shape[1] - 1)))


def report(title: str, df: pd.DataFrame, unit: str, groups: dict, extra: bool) -> None:
    s = stats(df, unit, groups)
    print(f"\n## {title}: {len(s['units'])} units, {s['products']} products with >= {MIN_BUYS} buys, {s['views']:,} views, {s['buys']:,} buys")
    print("global buys/view factor per unit: " + " ".join(f"{g:.3f}" for g in s["g"]))
    print(f"products: between chi2/df {s['no global factor']:.3f} (no global factor), {s['global factor']:.3f} (with); "
          f"within-unit halves {s['within']:.3f}; excess CV of the rate across units tau = {100 * s['tau']:.1f}%")
    print(f"{'grouping':<12}{'groups':>7}{'median n':>9}{'between':>9}{'within':>8}{'tau %':>7}")
    for name in groups:
        n, med, gb, gw, tau = s[f"group {name}"]
        print(f"{name:<12}{n:>7}{med:>9.0f}{gb:>9.3f}{gw:>8.3f}{100 * tau:>7.1f}")
    print(f"subcategory view-share chi2/df across units (trend in views, for contrast): {views_dispersion(df, unit, groups['subcategory']):.1f}")
    Zs, labels = s["Z subcategory"]  # does buys/view move with the subcategory's view trend?
    sub = df.assign(s=df["p"].map(lambda x: groups["subcategory"][x][0])).pivot_table(index="s", columns=unit, values="v", aggfunc="sum")
    sub = sub.reindex(index=labels, columns=s["units"]).fillna(0).to_numpy()
    lift = np.log((sub + 1) / (sub.sum(1, keepdims=True) + 1) / (sub.sum(0, keepdims=True) / sub.sum()))
    lift = lift - lift.mean(1, keepdims=True)
    top = np.abs(lift) > np.log(1.5)
    up = top & (lift > 0)
    print(f"corr(subcategory buys/view residual, log view lift) = {np.corrcoef(Zs.ravel(), lift.ravel())[0, 1]:+.3f} over {Zs.size} cells; "
          f"cells where views rose > x1.5: {up.sum()}, mean residual z {Zs[up].mean() if up.any() else float('nan'):+.2f}")
    worst = np.argsort(-(Zs ** 2).sum(1))[:5]
    print("largest subcategory residual series (z per unit): " + "; ".join(f"{labels[j]} " + " ".join(f"{z:+.1f}" for z in Zs[j]) for j in worst))
    if not extra:
        return
    Zp = s["R"] / np.sqrt(np.where(s["var"] > 0, s["var"], 1))
    Zs, _ = s["Z subcategory"]
    print("lag 1..7 autocorrelation, products:     " + " ".join(f"{a:+.3f}" for a in autocorr(Zp)))
    print("lag 1..7 autocorrelation, subcategories: " + " ".join(f"{a:+.3f}" for a in autocorr(Zs)))
    print(f"   (zero-sum residuals bias each lag by about {-1 / (len(s['units']) - 1):+.3f}; se about {1 / np.sqrt(Zs.size):.3f} for subcategories)")
    rng = np.random.default_rng(0)
    null = [pca_share(np.array([rng.permutation(row) for row in Zs])) for _ in range(200)]
    print(f"first 3 principal components of the subcategory x unit residuals: {100 * pca_share(Zs):.1f}% of variance; "
          f"day-shuffled null {100 * np.mean(null):.1f}% (95th pct {100 * np.quantile(null, 0.95):.1f}%)")


def vs_history(live: pd.DataFrame, cat: dict, skip: set) -> None:
    """Products with >= 30 buys in both: today's buys/view against the 60-day history's, one global scale."""
    hist = pull("history", True)
    l = live[~live["p"].map(lambda x: cat[x]["subcategory"] in skip)].groupby("p")[["v", "b"]].sum()
    j = l.join(hist.groupby("p")[["v", "b"]].sum(), how="inner", lsuffix="l", rsuffix="h")
    j = j[(j["bl"] >= 30) & (j["bh"] >= 30)]
    rl, rh = j["bl"] / j["vl"], j["bh"] / j["vh"]
    g = rl.mul(j["vl"]).sum() / j["vl"].sum() / (rh.mul(j["vh"]).sum() / j["vh"].sum())
    z = (rl - g * rh) / np.sqrt(rl * (1 - rl) / j["vl"] + g * g * rh * (1 - rh) / j["vh"])
    print(f"\n## today against history, {len(j)} products outside the trend subcategories: global ratio {g:.3f}, chi2/df {(z ** 2).mean():.3f}, "
          f"corr of log buys/view {np.corrcoef(np.log(rl), np.log(rh))[0, 1]:.3f}")


def main() -> None:
    which = sys.argv[1] if len(sys.argv) > 1 else "live"
    df = pull(which, "--cached" in sys.argv)
    cat = {r["product_id"]: r for r in json.loads((rt.ROOT / "data" / "catalog.json").read_text(encoding="utf-8"))}
    groups = {"subcategory": {p: (r["subcategory"],) for p, r in cat.items()}, "brand": {p: (r["brand"],) for p, r in cat.items()},
              "phrase": {p: phrases(r["description"]) for p, r in cat.items()}, "category": {p: (r["category"],) for p, r in cat.items()}}
    df = df[df["p"].isin(cat)]
    if which == "live":
        report("live, 2-hour blocks 09-21 UTC", df.assign(blk=(df["hr"] - 9) // 2), "blk", groups, True)
        report("live, 1-hour blocks", df, "hr", groups, True)
        trend = {"Aquariums", "Kettles", "Cutting Boards", "Bike Helmets", "Game Consoles"}  # view lift > x1.5 in a block, see above
        out = df[~df["p"].map(lambda x: cat[x]["subcategory"] in trend)]
        report("live, 2-hour blocks, trend subcategories left out", out.assign(blk=(out["hr"] - 9) // 2), "blk", groups, False)
        vs_history(df, cat, trend)
    else:
        report("history, days", df, "d", groups, True)
        report("history, weeks", df.assign(w=pd.to_datetime(df["d"]).dt.isocalendar().week.astype(int)), "w", groups, False)


if __name__ == "__main__":
    main()
