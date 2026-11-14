"""SHAP importance of ranker2 (click and buy boosters) on one fixed sample, per model snapshot.

    uv run python eda/shap/shap.py sample          # once: fixed sample from the cached train2 table (data/drift/table.npz)
    uv run python eda/shap/shap.py report          # all snapshots in data/shap/ plus the data/drift/ models, tables and noise floor

Click sample: 20,000 random impressions. Buy sample: every clicked impression in the table (what the buy model is fitted on).
TreeSHAP is LightGBM's own: predict(pred_contrib=True), in log-odds. Share = mean |SHAP| of a feature / sum over features.
"""
import re
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SHAP, DRIFT = ROOT / "data" / "shap", ROOT / "data" / "drift"
FEATURES = lgb.Booster(model_file=str(ROOT / "models" / "ranker2.txt")).feature_name()
# (label, window, variant): the drift test's models, trained on every row before the cut (UTC)
DRIFT_POINTS = [("cut 15:15", "1515_1815", "all"), ("cut 17:15", "1815_2115", "cut60"), ("cut 18:15", "1815_2115", "all")]


def sample() -> None:
    z = np.load(DRIFT / "table.npz")
    X, y = z["X"].astype(float), z["y"]
    idx = np.random.default_rng(0).choice(len(y), 20000, replace=False)
    np.savez(SHAP / "sample.npz", click=X[idx], buy=X[y == 1])
    print(f"click sample {len(idx)} rows ({int(y[idx].sum())} clicks), buy sample {int((y == 1).sum())} clicked rows")


def contrib(path: Path, X: np.ndarray) -> np.ndarray:
    """SHAP matrix (rows x features), one thread."""
    return lgb.Booster(model_file=str(path)).predict(X, pred_contrib=True, num_threads=1)[:, :-1]


def shares(s: np.ndarray) -> np.ndarray:
    m = np.abs(s).mean(0)
    return 100 * m / m.sum()


def direction(X: np.ndarray, s: np.ndarray, j: int) -> tuple[float, float, float]:
    """corr(value, SHAP), mean SHAP in the lowest and highest quintile of the value (NaN rows left out)."""
    ok = ~np.isnan(X[:, j])
    x, v = X[ok, j], s[ok, j]
    lo, hi = np.quantile(x, [0.2, 0.8])
    corr = np.corrcoef(x, v)[0, 1] if x.std() > 0 and v.std() > 0 else np.nan
    return corr, v[x <= lo].mean() if lo < hi else np.nan, v[x >= hi].mean() if lo < hi else np.nan


def snapshots(kind: str) -> list[tuple[str, Path]]:
    suffix = "_buy" if kind == "buy" else ""
    live = sorted(p for p in SHAP.glob(f"ranker2{suffix}_[0-9][0-9][0-9][0-9].txt"))
    out = [(f"{lab}z", DRIFT / "models" / w / v / f"ranker2{suffix}.txt") for lab, w, v in DRIFT_POINTS]
    return out + [(f"live {re.search(r'_(\d\d)(\d\d)\.txt', p.name).expand(r'\1:\2')}", p) for p in live]


def main() -> None:
    if sys.argv[1] == "sample":
        return sample()
    z = np.load(SHAP / "sample.npz")
    rng = np.random.default_rng(1)
    for kind in ("click", "buy"):
        X = z[kind]
        snaps = snapshots(kind)
        S = {lab: contrib(p, X) for lab, p in snaps}
        sh = {lab: shares(s) for lab, s in S.items()}
        labs = list(sh)
        last = labs[-1]
        # sampling noise: shares of the latest snapshot on 5 bootstrap resamples of the rows
        boot = np.array([shares(S[last][i]) for i in (rng.integers(0, len(X), len(X)) for _ in range(5))])
        # refit noise: same data and cut, three seeds (default, seed2, seed3), in both drift windows
        suffix = "_buy" if kind == "buy" else ""
        seeds = np.array([shares(contrib(DRIFT / "models" / w / v / f"ranker2{suffix}.txt", X)) for w in ("1515_1815", "1815_2115") for v in ("all", "seed2", "seed3")])
        refit = np.concatenate([seeds[:3].std(0, ddof=1)[None], seeds[3:].std(0, ddof=1)[None]]).mean(0)
        order = np.argsort(-sh[last])
        print(f"\n=== {kind} model, {len(X)} rows. share % per snapshot; change = {last} minus {labs[0]}; boot sd; refit sd; direction (corr, SHAP low q, SHAP high q)")
        print("feature".ljust(24) + "".join(l.rjust(13) for l in labs) + "   change  boot_sd refit_sd")
        for rank, j in enumerate(order):
            d = direction(X, S[last], j) if rank < 8 else None
            print(FEATURES[j].ljust(24) + "".join(f"{sh[l][j]:13.2f}" for l in labs) + f"{sh[last][j] - sh[labs[0]][j]:+9.2f}{boot[:, j].std(ddof=1):8.2f}{refit[j]:9.2f}"
                  + (f"   r={d[0]:+.2f} lo={d[1]:+.3f} hi={d[2]:+.3f}" if d else ""))
        print(f"max |change| first to last {np.abs(sh[last] - sh[labs[0]]).max():.2f}; sum |change|/2 (share moved) {np.abs(sh[last] - sh[labs[0]]).sum() / 2:.2f}; "
              f"mean boot sd {boot.std(0, ddof=1).mean():.2f}; mean refit sd {refit.mean():.2f}")
        # snapshot-to-snapshot movement between consecutive live snapshots
        for a, b in zip(labs, labs[1:]):
            print(f"  {a} -> {b}: largest move {np.abs(sh[b] - sh[a]).max():.2f} pts ({FEATURES[int(np.argmax(np.abs(sh[b] - sh[a])))]}), share moved {np.abs(sh[b] - sh[a]).sum() / 2:.2f}")


main()
