import lightgbm as lgb
import numpy as np

from q2q import train6
from q2q.strategies import ranker2, ranker6
from test_ranker2 import FakeState, request


def test_fallback_without_models(monkeypatch, tmp_path):
    monkeypatch.setattr(ranker6, "DIR", tmp_path)
    monkeypatch.setattr(ranker2, "MODEL", tmp_path / "none.txt")
    out = ranker6.Ranker6().recommend(request(["p1", "p4"]), FakeState())
    assert len(out) == len(set(out)) == 10 and "p0" not in out and not {"p3", "p9"} & set(out)


def test_bagged_models(monkeypatch, tmp_path):
    rng = np.random.default_rng(0)
    X = rng.normal(size=(400, len(ranker2.FEATURES)))
    y = (X[:, 1] + rng.normal(size=400) > 0).astype(int)
    monkeypatch.setattr(ranker6, "DIR", tmp_path)
    config = ({"objective": "binary", "num_leaves": 4, "min_data_in_leaf": 10, "verbose": -1, **train6.BAG}, 20, 3)
    models, _ = train6.fit(config, X, y)
    assert len(models) == 3
    train6.save("ranker6_click", models)
    train6.save("ranker6_buy", models[:2])
    click, buy = ranker6.files()
    assert len(click) == 3 and len(buy) == 2
    p = train6.predict(models, X)
    assert p.shape == (400,) and np.allclose(p, np.mean([m.predict(X) for m in models], axis=0))
    state = FakeState()
    out = ranker6.Ranker6().recommend(request(["p1", "p4", "p7"]), state)
    assert len(out) == len(set(out)) == 10 and all(state.available(x) for x in out) and not {"p3", "p9"} & set(out)
    train6.save("ranker6_buy", models[:1])  # fewer boosters: stale files removed
    assert len(ranker6.files()[1]) == 1 and isinstance(lgb.Booster(model_file=str(ranker6.files()[1][0])), lgb.Booster)
