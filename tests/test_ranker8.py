from q2q.strategies import ranker2, ranker3, ranker8, rules5
from q2q.strategy import Request
from test_ranker2 import FakeState


class State8(FakeState):
    """As the live State: today_carts and _today_carts, but no today_cart_last and no our_clicks_today."""
    def __init__(self):
        super().__init__()
        self._today_carts = {"known": {"p55": 2}}
        self.shoppers["known"].carted = {"p5": 4, "p55": 2}

    def today_carts(self, user_id):
        return self._today_carts.get(user_id, {})


def request(views, user="known"):
    return Request("r", 1200.0, user, False, "product", "web", "ES", list(views))


def test_inputs():
    assert not {"mins_since_cart_today", "clicked_ours_today"} & set(ranker8.FEATURES)
    assert set(ranker8.FEATURES) <= set(ranker8.ALL) and ranker8.COLS == sorted(ranker8.COLS)
    state, req = State8(), request(["p1", "p4"])
    c, r5 = ranker3.context(req, state), ranker8.rules5_ranks(req, state)
    top = [pid for _, pid, _ in rules5.STRATEGY.explain(req, state)]
    assert r5[top[0]] == 1 and len(r5) == len(top)
    row = ranker8.full_row(state.products[top[0]], req, c, r5)
    assert len(row) == len(ranker8.ALL) and row[-1] == 1
    outside = next(p for p in state.products.values() if p.id not in r5)
    assert ranker8.full_row(outside, req, c, r5)[-1] == ranker8.R5_OUT


def test_fallback_without_model(monkeypatch, tmp_path):
    monkeypatch.setattr(ranker8, "MODEL", tmp_path / "none.txt")
    monkeypatch.setattr(ranker2, "MODEL", tmp_path / "none2.txt")
    state, req = State8(), request(["p1", "p4"])
    assert ranker8.Ranker8().recommend(req, state) == ranker2.Ranker2().recommend(req, state)


def test_with_models(monkeypatch, tmp_path):
    r5_col = ranker8.FEATURES.index("rules5_rank") if "rules5_rank" in ranker8.FEATURES else None

    class Model:
        def predict(self, X):
            return [0.01 + 0.001 * row[1] + (0.1 / row[r5_col] if r5_col is not None else 0.0) for row in X]
    paths = [tmp_path / "click.txt", tmp_path / "buy.txt"]
    for p in paths:
        p.write_text("stub")
    monkeypatch.setattr(ranker8, "MODEL", paths[0])
    monkeypatch.setattr(ranker8, "BUY_MODEL", paths[1])
    state, s = State8(), ranker8.Ranker8()
    s.mtimes, s.models = tuple(p.stat().st_mtime for p in paths), (Model(), Model())
    for views, user in ((["p1", "p4", "p7"], "known"), ([], "known"), ([], "nobody"), (["zzz"], "nobody")):
        out = s.recommend(request(views, user), state)
        assert len(out) == len(set(out)) == 10
        assert all(state.available(p) for p in out) and (user != "known" or not {"p3", "p9"} & set(out))
    if r5_col is not None:
        req = request(["p1"])
        assert s.recommend(req, state)[0] == rules5.STRATEGY.recommend(req, state)[0]
