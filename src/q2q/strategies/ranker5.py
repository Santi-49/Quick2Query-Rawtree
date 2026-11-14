"""Ranker 5: ranker2 plus product-embedding features (q2q.emb, trained by q2q.train5).

Added inputs, cosines between the candidate's embedding and: the mean of the request's recent views, the closest
recent view, the last view, the mean of the shopper's history purchases and carts, the mean of today's earlier views.
NaN when either side has no embedding. The 30 nearest neighbours of the recent views' mean are extra candidates.

Score = P(click at slot 1) x P(purchase | click) x trend x price cut, as ranker2.
Until both model files and both embedding files exist it answers like ranker2.
"""
import json

import lightgbm as lgb
import numpy as np

from q2q import rt
from q2q.strategies import ranker2
from q2q.strategy import Strategy

MODEL = rt.ROOT / "models" / "ranker5.txt"
BUY_MODEL = rt.ROOT / "models" / "ranker5_buy.txt"
EMB = rt.ROOT / "data" / "emb" / "products.npy"
IDS = rt.ROOT / "data" / "emb" / "products.json"
FEATURES = ranker2.FEATURES + ["emb_mean_recent", "emb_max_recent", "emb_last", "emb_profile", "emb_today"]
NEIGHBOURS = 30
_emb = {"key": None, "value": None}


def embedding():
    """(E, index, ids) from EMB / IDS, reloaded when a file changes; None when missing."""
    key = tuple(p.stat().st_mtime if p.exists() else None for p in (EMB, IDS))
    if key != _emb["key"]:
        ids = json.loads(IDS.read_text(encoding="utf-8")) if all(key) else None
        _emb.update(key=key, value=(np.load(EMB), {p: i for i, p in enumerate(ids)}, ids) if ids else None)
    return _emb["value"]


def _mean(E, rows):
    return E[rows].mean(0) if rows else None


def context(req, state, live: bool = True, today: list[str] | None = None, emb=None) -> dict:
    """ranker2.context plus every product's cosine to the five session vectors (one 5000 x k product)."""
    c = ranker2.context(req, state, live=live, today=today)
    E, index, ids = emb or embedding()
    views = [index[v.id] for v in c["views"] if v.id in index]
    s = c["shopper"]
    profile = set(s.bought) | set(s.carted) if s else set()
    if live:  # training sees history carts only
        profile -= set(state.today_carts(req.user_id))
    vecs = [_mean(E, views), E[views[-1]] if c["views"] and c["views"][-1].id in index else None,
            _mean(E, [index[p] for p in profile if p in index]), _mean(E, [index[p] for p in c["today"] if p in index])]
    sims = np.full((len(E), 5), np.nan, dtype=np.float32)
    for k, v in zip((0, 2, 3, 4), vecs):
        if v is not None:
            sims[:, k] = E @ (v / max(float(np.linalg.norm(v)), 1e-9))
    if views:
        sims[:, 1] = (E @ E[views].T).max(1)
    near = [] if not views else np.argpartition(-sims[:, 0], NEIGHBOURS)[:NEIGHBOURS].tolist()
    c.update(emb_index=index, emb_sims=sims, emb_near=near, emb_ids=ids)
    return c


def features(p, slot: int, req, c: dict) -> list[float]:
    i = c["emb_index"].get(p.id)
    return ranker2.features(p, slot, req, c) + ([np.nan] * 5 if i is None else c["emb_sims"][i].tolist())


def candidates(state, c: dict) -> list:
    """ranker2's candidates plus the recent views' nearest neighbours (not bought, in stock)."""
    out = {p.id: p for p in ranker2.candidates(state, c)}
    for i in c["emb_near"]:
        pid = c["emb_ids"][i]
        if pid not in out and pid in state.products and pid not in c["bought"] and state.available(pid):
            out[pid] = state.products[pid]
    return list(out.values())


class Ranker5(Strategy):
    name = "ranker5"

    def __init__(self):
        self.models, self.mtimes = None, None

    def recommend(self, req, state):
        mtimes = tuple(m.stat().st_mtime if m.exists() else None for m in (MODEL, BUY_MODEL))
        if mtimes != self.mtimes:
            self.models = tuple(lgb.Booster(model_file=str(m)) for m in (MODEL, BUY_MODEL)) if all(mtimes) else None
            self.mtimes = mtimes
        emb = embedding()
        if self.models is None or emb is None:
            return ranker2.STRATEGY.recommend(req, state)
        c = context(req, state, emb=emb)
        cands = candidates(state, c)
        if not cands:
            return []
        X = [features(p, 1, req, c) for p in cands]
        click, buy = (m.predict(X) for m in self.models)
        scored = sorted(((float(k) * float(b) * state.trend.get(p.subcategory, 1.0) * (2 - state.price_cut.get(p.id, 1.0)), p.id)
                         for k, b, p in zip(click, buy, cands)), reverse=True)
        return [pid for _, pid in scored[:10]]


STRATEGY = Ranker5()
