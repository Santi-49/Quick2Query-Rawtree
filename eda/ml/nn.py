"""Second opinion on "deep" structure: a small CPU MLP with learned embeddings, on the live click label.

    uv run python eda/ml/nn.py

Embeddings for subcategory, brand, phrases (shared, summed), category, last viewed category, device, region, page;
no user or product IDs. A shopper/session tower and a product tower add a dot-product term to the MLP output.
Same time split as gbm.py. Prints held-out AUC against the LightGBM numbers and the nearest neighbours of the
subcategory and brand embeddings (are they grouped by category, or across categories?).
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch import nn

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import CATEG, ML  # noqa: E402
from gbm import META, auc, logloss, split  # noqa: E402

torch.set_num_threads(4)
torch.manual_seed(0)
EMB = {"p_sub": 8, "p_brand": 8, "p_cat": 4, "s_last_cat": 4, "device": 2, "region": 3, "page": 2}
USER_SIDE = ("device", "region", "page", "s_last_cat")


class Net(nn.Module):
    def __init__(self, sizes, n_num):
        super().__init__()
        self.emb = nn.ModuleDict({c: nn.Embedding(sizes[c], d) for c, d in EMB.items()})
        self.ph = nn.Embedding(sizes["ph"], 6)
        d_in = sum(EMB.values()) + 6 + n_num
        self.mlp = nn.Sequential(nn.Linear(d_in, 128), nn.ReLU(), nn.Dropout(0.2), nn.Linear(128, 64), nn.ReLU(), nn.Linear(64, 1))
        d_u, d_p = sum(EMB[c] for c in USER_SIDE), sum(EMB[c] for c in EMB if c not in USER_SIDE) + 6
        self.tu, self.tp = nn.Linear(d_u + n_num, 16), nn.Linear(d_p + n_num, 16)

    def forward(self, cat, num):
        e = {c: self.emb[c](cat[:, i]) for i, c in enumerate(EMB)}
        ph = self.ph(cat[:, len(EMB)]) + self.ph(cat[:, len(EMB) + 1])
        u = torch.cat([e[c] for c in USER_SIDE] + [num], 1)
        p = torch.cat([e[c] for c in EMB if c not in USER_SIDE] + [ph, num], 1)
        x = torch.cat(list(e.values()) + [ph, num], 1)
        return self.mlp(x).squeeze(1) + (self.tu(u) * self.tp(p)).sum(1) / 4


def prepare(T, fit_mask):
    cats = list(EMB) + ["p_ph1", "p_ph2"]
    C = np.stack([T[c].to_numpy() + 1 for c in cats], 1).clip(0)  # -1 (unknown) -> 0
    nums = [c for c in T.columns if c not in META and c not in CATEG and T[c].nunique() > 1]
    X = T[nums].to_numpy(dtype="float32")
    miss = np.isnan(X)
    flags = miss[:, miss.any(0)]
    X = np.sign(X) * np.log1p(np.abs(np.nan_to_num(X)))
    mu, sd = X[fit_mask].mean(0), X[fit_mask].std(0) + 1e-6
    X = np.concatenate([(X - mu) / sd, flags], 1).astype("float32")
    sizes = {c: int(C[:, i].max()) + 1 for i, c in enumerate(EMB)} | {"ph": int(C[:, -2:].max()) + 1}
    return torch.tensor(C, dtype=torch.long), torch.tensor(X), sizes


def predict(net, C, X, mask):
    net.eval()
    idx = np.where(mask)[0]
    with torch.no_grad():
        return np.concatenate([torch.sigmoid(net(C[idx[i:i + 65536]], X[idx[i:i + 65536]])).numpy() for i in range(0, len(idx), 65536)])


def neighbours(W, names, groups, k=4):
    """For each row, its k nearest rows by cosine and whether they share the group (category)."""
    Wn = W / (np.linalg.norm(W, axis=1, keepdims=True) + 1e-9)
    S = Wn @ Wn.T
    np.fill_diagonal(S, -2)
    nn_ = np.argsort(-S, 1)[:, :k]
    same = np.mean([[groups[i] == groups[j] for j in row] for i, row in enumerate(nn_)])
    return nn_, float(same)


def main():
    T = pd.read_parquet(ML / "table_live.parquet")
    fit_, val, test = split(T)
    C, X, sizes = prepare(T, fit_)
    y = torch.tensor(T.click.to_numpy(), dtype=torch.float32)
    net = Net(sizes, X.shape[1])
    opt = torch.optim.Adam(net.parameters(), lr=2e-3, weight_decay=1e-5)
    idx, best, best_state, bad = np.where(fit_)[0], 0.0, None, 0
    yv = T.click.to_numpy()
    for epoch in range(30):
        net.train()
        np.random.default_rng(epoch).shuffle(idx)
        for i in range(0, len(idx), 2048):
            b = idx[i:i + 2048]
            loss = nn.functional.binary_cross_entropy_with_logits(net(C[b], X[b]), y[b])
            opt.zero_grad()
            loss.backward()
            opt.step()
        a = auc(yv[val], predict(net, C, X, val))
        print(f"epoch {epoch}: val AUC {a:.4f}", flush=True)
        if a > best:
            best, best_state, bad = a, {k: v.clone() for k, v in net.state_dict().items()}, 0
        else:
            bad += 1
            if bad >= 4:
                break
    net.load_state_dict(best_state)
    p = predict(net, C, X, test)
    res = {"nn_test_auc": round(auc(yv[test], p), 4), "nn_test_logloss": round(logloss(yv[test], p), 5), "val_auc": round(best, 4)}
    gbm = json.loads((ML / "gbm_results.json").read_text()) if (ML / "gbm_results.json").exists() else {}
    print(f"\nNN held-out: {res}; LightGBM wide: {gbm.get('live/click/wide')}; base21: {gbm.get('live/click/base21')}")

    cat = pd.read_parquet(ML / "catalog.parquet")
    for col, name in [("p_sub", "sub"), ("p_brand", "brand")]:
        names = pd.factorize(cat[name])[1]
        cat_of = cat.groupby(name).cat.first()
        W = net.emb[col].weight.detach().numpy()[1:len(names) + 1]
        groups = [cat_of[n] for n in names]
        nn_, same = neighbours(W, names, groups)
        res[f"{name}_nn_same_category"] = round(same, 3)
        n_imp = T[col].value_counts()
        print(f"\n{name} embeddings: share of 4 nearest neighbours in the same category {same:.2f} (chance ~{1 / cat.cat.nunique():.2f})")
        for i in [int(i) for i in n_imp.index[:12] if 0 <= i < len(names)]:
            print(f"  {names[i]} ({groups[i]}): " + ", ".join(f"{names[j]} ({groups[j][:10]})" for j in nn_[i]))
    from q2q.state import FEATURES as PHRASES
    W = net.ph.weight.detach().numpy()[1:21]
    nn_, _ = neighbours(W, PHRASES, list(range(20)), k=3)
    print("\nphrase embeddings, 3 nearest:\n" + "\n".join(f"  {PHRASES[i]}: " + ", ".join(PHRASES[j] for j in nn_[i]) for i in range(20)))
    (ML / "nn_results.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
