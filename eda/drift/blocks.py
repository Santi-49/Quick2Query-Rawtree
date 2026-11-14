"""H-drift test 3: refit the H-loglinear click and purchase-given-click logits per 2-hour block of today.

    uv run python eda/drift/blocks.py            # pull feedback to now (cached in data/drift/pull.pkl), fit per block
    uv run python eda/drift/blocks.py --cached

Rows and indicators exactly as eda/linear/fit.py. Per block: coefficients and standard errors from the inverse of the
penalised Hessian. Per indicator: Cochran's Q across blocks (heterogeneity, chi2 with K-1 df) and the slope of the
coefficient on block index (inverse-variance weighted), as a z score. Writes nothing to models/.
"""
import importlib.util
import math
import sys

import numpy as np
from scipy.stats import chi2

from q2q import rt
from q2q.state import State
from q2q.strategies import linear1

spec = importlib.util.spec_from_file_location("linear_fit", rt.ROOT / "eda" / "linear" / "fit.py")
fit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fit)
fit.OUT = rt.ROOT / "data" / "drift"


def logit_se(X, y):
    m = fit.logit(X, y)
    Xa = np.hstack([X, np.ones((len(X), 1))])
    p = m.predict_proba(X)[:, 1]
    H = (Xa * (p * (1 - p))[:, None]).T @ Xa + np.diag([1.0] * X.shape[1] + [0.0])  # C=1: L2 penalty 1 on coefficients
    se = np.sqrt(np.diag(np.linalg.pinv(H)))[:-1]
    return m.coef_[0], se


def main():
    state = State()
    state.load()
    d = fit.pull("--cached" in sys.argv)
    X, _, y, b, t, g, _, high = fit.table(state, d)
    hour = (t / 1000 % 86400) // 3600
    blk = ((hour - 9) // 2).astype(int)
    blocks = [k for k in range(6) if (blk == k).sum() > 0]
    print(f"{len(y):,} rows, {y.sum():,} clicks, {b.sum():,} purchases; rows per block "
          + ", ".join(f"{9 + 2 * k:02d}-{11 + 2 * k:02d}h {int((blk == k).sum()):,} ({int(y[blk == k].sum())} clicks, {int(b[blk == k].sum())} buys)" for k in blocks))
    k_ = y == 1
    for label, mask, target in (("click", np.ones(len(y), bool), y), ("purchase | click", k_, b)):
        coefs, ses = [], []
        for k in blocks:
            m = mask & (blk == k)
            c, s = logit_se(X[m], target[m])
            coefs.append(c)
            ses.append(s)
        C, S = np.array(coefs), np.array(ses)
        n_on = np.array([[int(((blk == k) & mask & (X[:, j] > 0)).sum()) for j in range(X.shape[1])] for k in blocks])
        print(f"\n## {label}: multiplier exp(coef) per block (se on the log scale), Q across blocks, slope z per block")
        print(f"{'indicator':<20}" + "".join(f"{9 + 2 * k:>6}h    " for k in blocks) + f"{'Q':>7}{'p':>8}{'slope z':>9}")
        flagged = []
        for j, name in enumerate(linear1.NAMES):
            ok = n_on[:, j] >= 20  # blocks where the indicator is on in at least 20 rows
            cells = "".join(f"{math.exp(C[i, j]):>6.2f}({S[i, j]:.2f})" if ok[i] else f"{'-':>10}" for i in range(len(blocks)))
            if ok.sum() < 3:
                print(f"{name:<20}{cells}")
                continue
            c, w, x = C[ok, j], 1 / S[ok, j] ** 2, np.array(blocks, float)[ok]
            mean = (w * c).sum() / w.sum()
            Q = float((w * (c - mean) ** 2).sum())
            p = float(chi2.sf(Q, ok.sum() - 1))
            xm = (w * x).sum() / w.sum()
            slope = (w * (x - xm) * (c - mean)).sum() / (w * (x - xm) ** 2).sum()
            z = slope * math.sqrt((w * (x - xm) ** 2).sum())
            print(f"{name:<20}{cells}{Q:>7.1f}{p:>8.3f}{z:>+9.1f}")
            if p < 0.01 or abs(z) > 3:
                flagged.append(f"{name} (Q p={p:.3f}, slope z={z:+.1f})")
        print(f"flagged (Q p < 0.01 or |slope z| > 3; about {0.01 * len(linear1.NAMES):.1f} expected by chance from Q alone): " + (", ".join(flagged) or "none"))


if __name__ == "__main__":
    main()
