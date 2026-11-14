"""Train ranker6: ranker2's rows and features; each of the two models is an average of boosters.

    uv run python -m q2q.train6

Configurations are chosen inside the training rows, never on a later window: three expanding time folds (fit on
the oldest 55 / 70 / 85% of impressions, score the next 15%). A configuration with rounds = 0 stops early on the
newest 15% of its fold's fit rows; the final fit uses the median best round. The click configuration with the best
mean click AUC and the buy configuration with the best mean buy-given-click AUC are refitted on every row and saved.
"""
import time

import lightgbm as lgb
import numpy as np

from q2q import train2
from q2q.strategies import ranker6
from q2q.strategies.ranker2 import FEATURES
from q2q.train import PARAMS, auc

BAG = {"bagging_fraction": 0.8, "bagging_freq": 1, "feature_fraction": 0.8}
CLICK = {  # name -> (params, rounds (0 = early stopping), boosters)
    "r2": (PARAMS, 300, 1),
    "bag5": ({**PARAMS, **BAG}, 300, 5),
    "reg_bag5": ({**PARAMS, **BAG, "learning_rate": 0.02, "num_leaves": 7, "min_data_in_leaf": 400}, 0, 5),
}
BUY = {
    "r2": (None, None, 1),  # train2's rule: SMALL x 100 under 1,500 clicked rows, else PARAMS x 300
    "bag5": (None, None, 5),
    "reg_bag5": ({**train2.SMALL, **BAG, "learning_rate": 0.02, "num_leaves": 4, "min_data_in_leaf": 60, "lambda_l2": 20.0}, 0, 5),
    "reg2_bag5": ({**train2.SMALL, **BAG, "learning_rate": 0.02, "num_leaves": 3, "min_data_in_leaf": 120, "lambda_l2": 50.0}, 0, 5),
}
FOLDS = (0.55, 0.70, 0.85)
STEP = 0.15


def spec(config: tuple, n: int) -> tuple[dict, int, int]:
    params, rounds, k = config
    if params is None:  # ranker2's purchase rule, bagged when k > 1
        params, rounds = (train2.SMALL, 100) if n < 1500 else (PARAMS, 300)
        params = params if k == 1 else {**params, **BAG}
    return params, rounds, k


def fit(config: tuple, X, y, stop=None) -> tuple[list, int]:
    """Boosters and rounds. stop: (X, y) for early stopping when rounds = 0."""
    params, rounds, k = spec(config, len(y))
    models = []
    for seed in range(k):
        p = {**params, "seed": seed} if k > 1 else params
        if rounds:
            models.append(lgb.train(p, lgb.Dataset(X, y, feature_name=FEATURES), num_boost_round=rounds))
        else:
            m = lgb.train(p, lgb.Dataset(X, y, feature_name=FEATURES), num_boost_round=3000, valid_sets=[lgb.Dataset(stop[0], stop[1])],
                          callbacks=[lgb.early_stopping(100, verbose=False)])
            models.append(m)
    best = int(np.median([m.best_iteration or rounds for m in models]))
    return models, best


def predict(models, X) -> np.ndarray:
    return np.mean([m.predict(X, num_iteration=m.best_iteration or None) for m in models], axis=0)


def select(X, y, b, t, g) -> tuple[str, str, int, int]:
    """Time folds inside the rows: per configuration mean AUCs, and first / top 3 of the purchased product per pair."""
    q = lambda f: np.quantile(t, f)  # noqa: E731
    res, rounds = {}, {}
    for f in FOLDS:
        tr, va = t <= q(f), (t > q(f)) & (t <= q(f + STEP))
        stop = tr & (t > q(f * 0.85))
        fit_ = tr & ~stop
        X1 = X[va].copy()
        X1[:, 0] = 1  # every candidate scored at slot 1, as live
        preds = {}
        for kind, configs, lab, rows in (("click", CLICK, y, np.ones(len(y), bool)), ("buy", BUY, b, y == 1)):
            for name, config in configs.items():
                tr_all, fr, st = tr & rows, fit_ & rows, stop & rows
                if config[1] == 0:
                    models, best = fit(config, X[fr], lab[fr], (X[st], lab[st]))
                else:
                    models, best = fit(config, X[tr_all], lab[tr_all])
                rounds.setdefault((kind, name), []).append(best)
                v = va & rows
                res.setdefault((kind, name), []).append(auc(lab[v], predict(models, X[v])))
                preds[(kind, name)] = predict(models, X1)
        for kc in CLICK:
            for kb in BUY:
                first, top3, n = train2.ranked(preds[("click", kc)] * preds[("buy", kb)], b[va], g[va])
                res.setdefault(("pair", kc, kb), []).append((first, top3, n))
        print(f"fold {f:.2f}: fit {tr.sum():,} rows ({(tr & (y == 1)).sum()} clicks), score {va.sum():,} rows ({(va & (y == 1)).sum()} clicks, "
              f"{(va & (b == 1)).sum()} purchases)", flush=True)
    for kind, configs in (("click", CLICK), ("buy", BUY)):
        for name in configs:
            a = res[(kind, name)]
            print(f"  {kind:<5} {name:<10} AUC by fold " + " / ".join(f"{x:.3f}" for x in a) + f", mean {np.mean(a):.3f}; rounds {rounds[(kind, name)]}")
    for kc in CLICK:
        for kb in BUY:
            r = res[("pair", kc, kb)]
            print(f"  pair {kc:<9} x {kb:<10} first {np.mean([x[0] for x in r]):5.1f}%  top 3 {np.mean([x[1] for x in r]):5.1f}%  "
                  f"({sum(x[2] for x in r)} requests over the folds)")
    kc = max(CLICK, key=lambda n: np.mean(res[("click", n)]))
    kb = max(BUY, key=lambda n: np.mean(res[("buy", n)]))
    return kc, kb, int(np.median(rounds[("click", kc)])), int(np.median(rounds[("buy", kb)]))


def save(prefix: str, models: list) -> None:
    for old in ranker6.DIR.glob(f"{prefix}_*.txt"):
        old.unlink()
    for i, m in enumerate(models):
        path = ranker6.DIR / f"{prefix}_{i}.txt"
        tmp = path.with_suffix(".tmp")
        m.save_model(str(tmp))
        tmp.replace(path)


def train(state, table=None) -> tuple[str, str]:
    """table: train2.table(state) when already built."""
    start = time.time()
    X, y, b, t, g = table if table is not None else train2.table(state)
    print(f"table {len(y):,} rows, {y.sum():,} clicks, {b.sum():,} purchases", flush=True)
    kc, kb, rc, rb = select(X, y, b, t, g)
    print(f"chosen: click {kc}, buy {kb}", flush=True)
    ranker6.DIR.mkdir(parents=True, exist_ok=True)
    for prefix, configs, name, r, rows, lab in (("ranker6_click", CLICK, kc, rc, np.ones(len(y), bool), y), ("ranker6_buy", BUY, kb, rb, y == 1, b)):
        params, rounds, k = configs[name]
        config = (params, rounds or r, k) if params is not None else configs[name]
        save(prefix, fit(config, X[rows], lab[rows])[0])
    print(f"saved ranker6 models in {time.time() - start:.0f} s", flush=True)
    return kc, kb


if __name__ == "__main__":
    from q2q.state import State
    st = State()
    st.load()
    train(st)
