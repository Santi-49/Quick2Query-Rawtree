"""Does adding the history carousel log to our live feedback help ranker2? (H-history-pretrain)

    uv run python eda/ml/history_plus_live.py

Tables: data/ml/table_hist.parquet and table_live.parquet (eda/ml/build.py). Features: the closest columns to
ranker2.FEATURES that both tables have. Rows where the shopper bought the product in history are dropped (as
train2 does), which also removes "bought before" from both tables. Repeat-buy rate, per-shopper purchase counts and
carousel CTR are not used. Newest 20% of live requests held out by time; train2's LightGBM settings (300 rounds,
fit_buy) for every variant, 3 seeds each. Score = P(click at slot 1) x P(buy | click), ranked inside each held-out
request with a purchase. Then one small MLP (click and buy nets, early stopping) on live only and on variant (c).
"""
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
import torch
from torch import nn

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import BASE, ML  # noqa: E402
from q2q.train import PARAMS, auc  # noqa: E402
from q2q.train2 import SMALL, ranked  # noqa: E402

# ranker2's 13 extra features -> closest table columns; is_first_view, is_later_view, in_main_cat, viewed_today and
# sub_viewed_today are not in the study tables (and "today" does not exist in the history sample)
EXTRA = ["phrase_share", "session_phrase_overlap", "carted_not_bought", "coview", "shopper_cart_rate", "cat_carts", "brand_share", "sub_share"]
FEATS = BASE + EXTRA
SEEDS = (1, 2, 3)
HW = 0.25


def load(tag):
    T = pd.read_parquet(ML / f"table_{tag}.parquet")
    T = T[T.x_p_bought.fillna(0) == 0].reset_index(drop=True)
    X = T[BASE].astype(float).copy()
    X["phrase_share"] = T.x_ph_share
    X["session_phrase_overlap"] = T.s_ph_overlap_sum.clip(upper=4)
    X["carted_not_bought"] = T.x_p_carts.fillna(0).clip(upper=3)
    X["coview"] = np.log1p(T.s_coview_any)
    X["shopper_cart_rate"] = T.u_sess_cart_rate
    X["cat_carts"] = np.log1p(T.x_cat_c)
    X["brand_share"], X["sub_share"] = T.x_brand_share, T.x_sub_share
    return X[FEATS], T.click.to_numpy(int), T.buy.to_numpy(int), T.t.to_numpy(float), pd.factorize(T.rid)[0]


def fit_buy(X, b, params, w=None, init=None):
    small = len(b) < 1500
    p = {**SMALL, "seed": params["seed"], "num_threads": 4} if small else params
    return lgb.train(p, lgb.Dataset(X, b, weight=w), num_boost_round=100 if small else 300, init_model=init)


def metrics(click_m, buy_m, Xt, yt, bt, gt):
    X1 = Xt.copy()
    X1["slot"] = 1
    k = click_m.predict(Xt)
    first, top3, n = ranked(click_m.predict(X1) * buy_m.predict(X1), bt, gt)
    return auc(yt, k), auc(bt[yt == 1], buy_m.predict(Xt[yt == 1])), first, top3, n


def gbm_variant(name, H, L, seed):
    (Xh, yh, bh), (Xl, yl, bl) = H, L
    params = {**PARAMS, "seed": seed, "num_threads": 4}
    click = lambda X, y, w=None, init=None: lgb.train(params, lgb.Dataset(X, y, weight=w), 300, init_model=init)  # noqa: E731
    if name == "a live only":
        return click(Xl, yl), fit_buy(Xl[yl == 1], bl[yl == 1], params)
    if name == "e history only":
        return click(Xh, yh), fit_buy(Xh[yh == 1], bh[yh == 1], params)
    if name == "d history, then boost on live":
        ch, bh_ = click(Xh, yh), fit_buy(Xh[yh == 1], bh[yh == 1], params)
        return click(Xl, yl, init=ch), fit_buy(Xl[yl == 1], bl[yl == 1], params, init=bh_)
    X, y, b = pd.concat([Xh, Xl], ignore_index=True), np.r_[yh, yl], np.r_[bh, bl]
    if name == "b pooled + is_live":
        X["is_live"] = np.r_[np.zeros(len(yh)), np.ones(len(yl))]
        return click(X, y), fit_buy(X[y == 1], b[y == 1], params)
    w = np.r_[np.full(len(yh), HW), np.ones(len(yl))]  # c
    return click(X, y, w), fit_buy(X[y == 1], b[y == 1], params, w[y == 1])


class MLP(nn.Module):
    def __init__(self, d):
        super().__init__()
        self.f = nn.Sequential(nn.Linear(d, 64), nn.ReLU(), nn.Dropout(0.2), nn.Linear(64, 32), nn.ReLU(), nn.Linear(32, 1))

    def forward(self, x):
        return self.f(x).squeeze(1)


def tensor(X, mu=None, sd=None):
    A = X.to_numpy(dtype="float32")
    miss = np.isnan(A[:, :])
    A = np.nan_to_num(A)
    A = np.sign(A) * np.log1p(np.abs(A))
    onehot = np.stack([X.page == 0, X.page == 1, X.page == 2, X.device == 0, X.device == 1, X.device == 2], 1)
    if mu is None:
        mu, sd = A.mean(0), A.std(0) + 1e-6
    A = np.concatenate([np.clip((A - mu) / sd, -8, 8), miss[:, [FEATS.index(c) for c in ("phrase_share", "shopper_cart_rate", "cat_carts", "cat_share")]], onehot], 1)
    return torch.tensor(A.astype("float32")), mu, sd


def train_net(X, y, w, Xv, yv, seed):
    torch.manual_seed(seed)
    net = MLP(X.shape[1])
    opt = torch.optim.Adam(net.parameters(), lr=2e-3, weight_decay=1e-5)
    yt, wt = torch.tensor(y, dtype=torch.float32), torch.tensor(w, dtype=torch.float32)
    idx, best, state, bad = np.arange(len(y)), -1.0, None, 0
    batch = 2048 if len(y) > 50000 else 256
    for epoch in range(40):
        net.train()
        np.random.default_rng(seed * 100 + epoch).shuffle(idx)
        for i in range(0, len(idx), batch):
            j = idx[i:i + batch]
            loss = (nn.functional.binary_cross_entropy_with_logits(net(X[j]), yt[j], reduction="none") * wt[j]).sum() / wt[j].sum()
            opt.zero_grad()
            loss.backward()
            opt.step()
        a = auc(yv, predict(net, Xv))
        if a > best:
            best, state, bad = a, {k: v.clone() for k, v in net.state_dict().items()}, 0
        else:
            bad += 1
            if bad >= 4:
                break
    net.load_state_dict(state)
    return net


def predict(net, X):
    net.eval()
    with torch.no_grad():
        return torch.sigmoid(torch.cat([net(X[i:i + 65536]) for i in range(0, len(X), 65536)])).numpy()


def nn_variant(hist_w, H, Lfit, Lval, test, seed):
    """Click and buy nets on history (weight hist_w; 0 = left out) + oldest 70% of live, early-stopped on live 70-80%."""
    (Xh, yh, bh), (Xl, yl, bl), (Xv, yv, bv) = H, Lfit, Lval
    Xt, yt, bt, gt = test
    if hist_w:
        X, y, b, w = pd.concat([Xh, Xl], ignore_index=True), np.r_[yh, yl], np.r_[bh, bl], np.r_[np.full(len(yh), hist_w), np.ones(len(yl))]
    else:
        X, y, b, w = Xl.reset_index(drop=True), yl, bl, np.ones(len(yl))
    A, mu, sd = tensor(X)
    V, T_ = tensor(Xv, mu, sd)[0], tensor(Xt, mu, sd)[0]
    X1 = Xt.copy()
    X1["slot"] = 1
    T1 = tensor(X1, mu, sd)[0]
    click = train_net(A, y, w, V, yv, seed)
    c = y == 1
    buy = train_net(A[torch.tensor(c)], b[c], w[c], V[torch.tensor(yv == 1)], bv[yv == 1], seed)
    first, top3, n = ranked(predict(click, T1) * predict(buy, T1), bt, gt)
    return auc(yt, predict(click, T_)), auc(bt[yt == 1], predict(buy, T_[torch.tensor(yt == 1)])), first, top3, n


def show(name, rs):
    r = np.array([x[:4] for x in rs])
    cells = [f"{m:.3f} ± {(hi - lo) / 2:.3f}" if j < 2 else f"{m:.1f} ± {(hi - lo) / 2:.1f}" for j, (m, lo, hi) in enumerate(zip(r.mean(0), r.min(0), r.max(0)))]
    print(f"| {name} | " + " | ".join(cells) + f" | {rs[0][4]} |", flush=True)


def main():
    Xh, yh, bh, _, _ = load("hist")
    Xl, yl, bl, tl, gl = load("live")
    print(f"history {len(yh):,} rows, {yh.sum()} clicks, {bh.sum()} buys; live {len(yl):,} rows, {yl.sum()} clicks, {bl.sum()} buys", flush=True)
    rt = pd.Series(tl).groupby(gl).first()
    q70, q80 = rt.quantile([0.7, 0.8])
    new, fit70 = tl > q80, tl <= q70
    old, val = ~new, (tl > q70) & ~new
    test = (Xl[new].reset_index(drop=True), yl[new], bl[new], gl[new])
    print(f"held-out: {new.sum():,} rows, {yl[new].sum()} clicks, {bl[new].sum()} buys; live fitted on {yl[old].sum()} clicks, history {yh.sum()} clicks", flush=True)
    print("| variant | click AUC | buy given click AUC | purchased ranked 1st % | in top 3 % | requests |\n|---|---|---|---|---|---|")
    H, L = (Xh, yh, bh), (Xl[old].reset_index(drop=True), yl[old], bl[old])
    for name in ["a live only", "b pooled + is_live", f"c pooled, history weight {HW}", "d history, then boost on live", "e history only"]:
        rs = []
        for s in SEEDS:
            click_m, buy_m = gbm_variant(name if not name.startswith("c") else "c", H, L, s)
            Xt = test[0].assign(is_live=1.0) if name.startswith("b") else test[0]
            rs.append(metrics(click_m, buy_m, Xt, *test[1:]))
        show("LightGBM " + name, rs)
    Lfit, Lval = (Xl[fit70].reset_index(drop=True), yl[fit70], bl[fit70]), (Xl[val].reset_index(drop=True), yl[val], bl[val])
    for hw, name in [(0, "a live only"), (HW, f"c history weight {HW}")]:
        show("MLP " + name, [nn_variant(hw, H, Lfit, Lval, test, s) for s in SEEDS])


if __name__ == "__main__":
    main()
