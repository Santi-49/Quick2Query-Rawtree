"""LightGBM on the wide impression table: scores, importance (gain, permutation, SHAP), interactions, partial dependence.

    uv run python eda/ml/gbm.py

Time split per table: fit on the oldest 70% of requests, early-stop on the next 10%, score on the newest 20%.
(a) live only, (b) history only, (c) the history model scored on the live test rows. Each against the 21 ranker
features (BASE) on the same rows. Results: data/ml/gbm_results.json and stdout.
"""
import json
import sys
import time
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import BASE, CATEG, ML  # noqa: E402

META = ["rid", "t", "u", "mv", "p", "click", "buy"]
PARAMS = {"objective": "binary", "learning_rate": 0.03, "num_leaves": 15, "min_data_in_leaf": 200, "feature_fraction": 0.7, "bagging_fraction": 0.8,
          "bagging_freq": 1, "lambda_l2": 10.0, "cat_smooth": 50, "min_data_per_group": 200, "max_cat_to_onehot": 4, "verbose": -1, "num_threads": 4, "seed": 7}
# signals already in docs/SIMULATOR.md or the 21 ranker features (or trivial variants of them)
KNOWN = set(BASE) | {"inv_log_slot", "seg_south", "region", "x_p_bought", "x_p_buys", "x_p_views", "x_cat_share", "x_cat_v", "x_cat_rank", "p_bpv", "p_cat",
                     "l_sub_trend", "l_price_ratio", "l_mins_price", "s_n_same_cat", "s_n_same_sub", "s_n_same_p", "x_sub_v", "p_age_days", "hour", "dow"}


def auc(y, s):
    r = pd.Series(s).rank().to_numpy()
    pos = y.sum()
    return float((r[y == 1].sum() - pos * (pos + 1) / 2) / (pos * (len(y) - pos)))


def logloss(y, p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def split(T):
    """Request-time quantiles: 0-70% fit, 70-80% early stopping, 80-100% test."""
    q = T.groupby("rid").t.first().quantile([0.7, 0.8]).to_numpy()
    return (T.t <= q[0]).to_numpy(), ((T.t > q[0]) & (T.t <= q[1])).to_numpy(), (T.t > q[1]).to_numpy()


def fit(T, cols, label, parts):
    fit_, val, _ = parts
    cat = [c for c in cols if c in CATEG]
    ds = lgb.Dataset(T.loc[fit_, cols], T.loc[fit_, label], categorical_feature=cat, free_raw_data=True)
    dv = lgb.Dataset(T.loc[val, cols], T.loc[val, label], reference=ds, categorical_feature=cat)
    return lgb.train(PARAMS, ds, 2000, valid_sets=[dv], callbacks=[lgb.early_stopping(100, verbose=False)])


def score(m, T, cols, label, mask):
    p = m.predict(T.loc[mask, cols], num_iteration=m.best_iteration)
    y = T.loc[mask, label].to_numpy()
    return {"auc": round(auc(y, p), 4), "logloss": round(logloss(y, p), 5), "pos": int(y.sum()), "rows": int(mask.sum()), "trees": m.best_iteration}


def permutation(m, X, y, reps=2, seed=0):
    """AUC drop when one feature is shuffled on the held-out rows (mean over reps)."""
    rng = np.random.default_rng(seed)
    base = auc(y, m.predict(X, num_iteration=m.best_iteration))
    out = {}
    for c in X.columns:
        keep, drops = X[c].to_numpy().copy(), []
        for _ in range(reps):
            X[c] = rng.permutation(keep)
            drops.append(base - auc(y, m.predict(X, num_iteration=m.best_iteration)))
        X[c] = keep
        out[c] = float(np.mean(drops))
    return base, out


def h_stat(m, X, feats, n=300, seed=0):
    """Friedman's H^2 for every pair of feats on n rows (centered partial dependence)."""
    S = X.sample(n, random_state=seed).reset_index(drop=True)
    it = m.best_iteration

    def pd_(fs):
        rows = pd.concat([S] * n, ignore_index=True)
        for f in fs:
            rows[f] = np.repeat(S[f].to_numpy(), n)  # block k: every sample row with f set to row k's value
        v = m.predict(rows, num_iteration=it, raw_score=True).reshape(n, n).mean(1)
        return v - v.mean()
    one = {f: pd_([f]) for f in feats}
    out = []
    for i, a in enumerate(feats):
        for b in feats[i + 1:]:
            ab = pd_([a, b])
            out.append((a, b, float(((ab - one[a] - one[b]) ** 2).sum() / max((ab ** 2).sum(), 1e-12))))
    return sorted(out, key=lambda x: -x[2])


def pd_table(T, m, cols, f, sample):
    """Raw counts per bin on all live rows + model partial dependence (click prob at slot 1) at the bin median."""
    x = T[f]
    if x.nunique() <= 8:
        bins = x.fillna(-999)
    else:
        edges = np.unique(np.nanquantile(x, [0, .2, .4, .6, .8, .9, .97, 1]))
        bins = pd.cut(x, edges, include_lowest=True, duplicates="drop").astype(str).where(x.notna(), "NaN")
    g = T.assign(b=bins, w=1 / np.log2(T.slot + 1)).groupby("b", observed=True).agg(n=("click", "size"), w=("w", "sum"), clicks=("click", "sum"),
                                                                                  buys=("buy", "sum"), med=(f, "median"))
    g["click_pw"], g["buy_pw"] = 100 * g.clicks / g.w, 100 * g.buys / g.w
    S = sample.copy()
    S["slot"] = 1
    pdv = []
    for v in g.med:
        S[f] = v
        pdv.append(100 * float(m.predict(S[cols], num_iteration=m.best_iteration).mean()))
    g["pd_click_slot1"] = pdv
    return g.round(3).reset_index().astype({"b": str})


def main():
    start, R = time.time(), {}
    hist = pd.read_parquet(ML / "table_hist.parquet")
    feats_h = [c for c in hist.columns if c not in META]
    ph = split(hist)
    models_h = {}
    for label in ["click", "buy"]:
        for name, cols in [("wide", feats_h), ("base21", BASE)]:
            m = fit(hist, cols, label, ph)
            models_h[(label, name)] = m
            R[f"hist/{label}/{name}"] = score(m, hist, cols, label, ph[2])
            print(f"hist {label} {name}: {R[f'hist/{label}/{name}']}", flush=True)
    del hist
    live = pd.read_parquet(ML / "table_live.parquet")
    feats = [c for c in live.columns if c not in META and live[c].nunique() > 1]
    pl = split(live)
    models = {}
    for label in ["click", "buy"]:
        for name, cols in [("wide", feats), ("base21", BASE), ("wide_no_live_state", [c for c in feats if not c.startswith("l_")])]:
            m = fit(live, cols, label, pl)
            models[(label, name)] = m
            R[f"live/{label}/{name}"] = score(m, live, cols, label, pl[2])
            print(f"live {label} {name}: {R[f'live/{label}/{name}']}", flush=True)
        for name, cols in [("wide", feats_h), ("base21", BASE)]:
            R[f"hist->live/{label}/{name}"] = score(models_h[(label, name)], live, cols, label, pl[2])
            print(f"hist model on live test {label} {name}: {R[f'hist->live/{label}/{name}']}", flush=True)
    y_slot = live.loc[pl[2], "click"].to_numpy()
    R["live/click/slot_only_auc"] = round(auc(y_slot, -live.loc[pl[2], "slot"].to_numpy()), 4)
    models[("click", "wide")].save_model(str(ML / "gbm_live_click.txt"))

    imp = {}
    for label in ["click", "buy"]:
        m = models[(label, "wide")]
        X, y = live.loc[pl[2], feats].reset_index(drop=True), live.loc[pl[2], label].to_numpy()
        base, perm = permutation(m, X, y)
        gain = dict(zip(feats, m.feature_importance("gain")))
        S = X.sample(min(20000, len(X)), random_state=1)
        shap = np.abs(m.predict(S, num_iteration=m.best_iteration, pred_contrib=True)[:, :-1]).mean(0)
        hm = models_h[(label, "wide")]
        perm_h = permutation(hm, live.loc[pl[2], feats_h].reset_index(drop=True), y, reps=1)[1]
        imp[label] = pd.DataFrame({"perm_auc_drop": perm, "gain_pct": {k: 100 * v / sum(gain.values()) for k, v in gain.items()},
                                   "mean_abs_shap": dict(zip(feats, shap)), "hist_model_perm_on_live": perm_h}).fillna(0)
        imp[label]["known"] = [c in KNOWN for c in imp[label].index]
        imp[label] = imp[label].sort_values("perm_auc_drop", ascending=False)
        imp[label].to_csv(ML / f"importance_{label}.csv")
        print(f"\n{label}: held-out AUC {base:.4f}; top 40 by permutation\n{imp[label].head(40).round(5).to_string()}", flush=True)

    top = list(imp["click"].index[:25])
    m = models[("click", "wide")]
    H = h_stat(m, live.loc[pl[2], feats], top)
    R["interactions_click"] = H[:20]
    print("\ntop interactions (H^2):\n" + "\n".join(f"{a} x {b}: {h:.3f}" for a, b, h in H[:20]), flush=True)

    new = [c for c in imp["click"].index if not imp["click"].loc[c, "known"]][:15]
    sample = live.loc[pl[2], feats].sample(3000, random_state=2)
    R["pd"] = {}
    for f in new:
        tab = pd_table(live, m, feats, f, sample)
        R["pd"][f] = tab.to_dict("records")
        print(f"\n{f}\n{tab.to_string(index=False)}", flush=True)
    (ML / "gbm_results.json").write_text(json.dumps(R, indent=1, default=str))
    print(f"\ndone in {time.time() - start:.0f} s")


if __name__ == "__main__":
    main()
