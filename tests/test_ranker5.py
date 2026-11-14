import json
import math

import numpy as np

from q2q.strategies import ranker2, ranker5
from q2q.strategy import Request
from test_ranker2 import FakeState


class State5(FakeState):
    def today_carts(self, user_id):
        return {}


def emb_files(tmp_path, monkeypatch):
    """p0..p49 embedded (p50..p59 not): p1 and p42 identical, p2 opposite to p1."""
    rng = np.random.default_rng(0)
    E = rng.normal(size=(50, 8)).astype(np.float32)
    E[42], E[2] = E[1], -E[1]
    E /= np.linalg.norm(E, axis=1, keepdims=True)
    np.save(tmp_path / "e.npy", E)
    (tmp_path / "e.json").write_text(json.dumps([f"p{i}" for i in range(50)]))
    monkeypatch.setattr(ranker5, "EMB", tmp_path / "e.npy")
    monkeypatch.setattr(ranker5, "IDS", tmp_path / "e.json")


def request(views, user="known"):
    return Request("r", 0.0, user, False, "product", "web", "ES", list(views))


def named(p, c, req):
    row = ranker5.features(p, 1, req, c)
    assert len(row) == len(ranker5.FEATURES)
    return dict(zip(ranker5.FEATURES, row))


def test_features(tmp_path, monkeypatch):
    emb_files(tmp_path, monkeypatch)
    state, req = State5(), request(["p4", "p1"])
    c = ranker5.context(req, state)
    f = named(state.products["p42"], c, req)
    assert abs(f["emb_last"] - 1) < 1e-5 and abs(f["emb_max_recent"] - 1) < 1e-5 and f["emb_mean_recent"] < 1
    assert abs(named(state.products["p2"], c, req)["emb_last"] + 1) < 1e-5
    assert all(math.isnan(v) for k, v in named(state.products["p55"], c, req).items() if k.startswith("emb_"))  # no embedding
    assert not math.isnan(f["emb_profile"]) and not math.isnan(f["emb_today"])  # history p3, p9, p5; today p20
    cold = ranker5.context(request([], "nobody"), state)
    g = named(state.products["p42"], cold, req)
    assert all(math.isnan(g[k]) for k in ("emb_mean_recent", "emb_max_recent", "emb_last", "emb_profile")) and cold["emb_near"] == []
    assert "p42" in {p.id for p in ranker5.candidates(state, c)}


def test_fallback_without_files(monkeypatch, tmp_path):
    monkeypatch.setattr(ranker5, "EMB", tmp_path / "none.npy")
    monkeypatch.setattr(ranker2, "MODEL", tmp_path / "none2.txt")
    out = ranker5.Ranker5().recommend(request(["p1", "p4"]), State5())
    assert len(out) == len(set(out)) == 10 and "p0" not in out and not {"p3", "p9"} & set(out)


def test_with_models(monkeypatch, tmp_path):
    emb_files(tmp_path, monkeypatch)

    class Model:
        def predict(self, X):
            return [0.01 + 0.05 * (0 if math.isnan(row[len(ranker2.FEATURES) + 2]) else row[len(ranker2.FEATURES) + 2]) for row in X]  # emb_last
    paths = [tmp_path / "click.txt", tmp_path / "buy.txt"]
    for p in paths:
        p.write_text("stub")
    monkeypatch.setattr(ranker5, "MODEL", paths[0])
    monkeypatch.setattr(ranker5, "BUY_MODEL", paths[1])
    state, s = State5(), ranker5.Ranker5()
    s.mtimes, s.models = tuple(p.stat().st_mtime for p in paths), (Model(), Model())
    for views, user in ((["p1", "p4", "p7"], "known"), ([], "known"), ([], "nobody"), (["zzz"], "nobody")):
        out = s.recommend(request(views, user), state)
        assert len(out) == len(set(out)) == 10
        assert all(state.available(p) for p in out) and not {"p3", "p9"} & set(out)
    assert set(s.recommend(request(["p4", "p1"]), state)[:2]) == {"p1", "p42"}
