import math

from q2q.strategies import ranker2, ranker3
from q2q.strategy import Request
from test_ranker2 import FakeState


class State3(FakeState):
    def __init__(self):
        super().__init__()
        self.carts = {"known": {"p55": 2, "p3": 1}}  # p55 carted today; p3 bought in history
        self.shoppers["known"].carted = {"p5": 4, "p55": 2}  # live Shopper: history + today
        self.our_clicks_today = {"known": {"p33", "p3"}}

    def today_carts(self, user_id):
        return self.carts.get(user_id, {})

    def today_cart_last(self, user_id):
        return {"p55": 600.0} if user_id == "known" else {}


def request(views, user="known"):
    return Request("r", 1200.0, user, False, "product", "web", "ES", list(views))


def named(p, c, req):
    row = ranker3.features(p, 1, req, c)
    assert len(row) == len(ranker3.FEATURES)
    return dict(zip(ranker3.FEATURES, row))


def test_features():
    state, req = State3(), request(["p1", "p4", "p1"])
    c = ranker3.context(req, state)
    f = named(state.products["p55"], c, req)
    assert f["carted_today"] == 2 and f["mins_since_cart_today"] == 10 and f["carted_not_bought"] == 0  # today's carts are not history carts
    assert not f["single_view_session"] and f["n_recent_views"] == 2
    assert f["log_bpv"] == math.log((5 + 3.4) / (100 + 20))
    h = named(state.products["p5"], c, req)
    assert h["carted_not_bought"] == 3 and h["cart_x_high_cart_rate"] and math.isnan(h["mins_since_cart_today"])
    assert named(state.products["p33"], c, req)["clicked_ours_today"] and "p3" not in c["our"] and "p3" not in c["tc"]
    other = named(state.products["p1"], c, req)  # p55 is c1/s1, p1 too
    assert other["cat_carted_today"] == 1 and other["sub_carted_today"] == 1 and f["cat_carted_today"] == 0


def test_today_cart_is_a_candidate():
    state = State3()
    state.by_category, state.shoppers["known"].carted = {}, {}  # only today's cart brings p55 (s1; the view p2 is s2)
    c = ranker3.context(request(["p2"]), state)
    assert "p55" not in {p.id for p in ranker2.candidates(state, c)}
    assert "p55" in {p.id for p in ranker3.candidates(state, c)}


def test_fallback_without_model(monkeypatch, tmp_path):
    monkeypatch.setattr(ranker3, "MODEL", tmp_path / "none.txt")
    monkeypatch.setattr(ranker2, "MODEL", tmp_path / "none2.txt")
    out = ranker3.Ranker3().recommend(request(["p1", "p4"]), State3())
    assert len(out) == len(set(out)) == 10 and "p0" not in out and not {"p3", "p9"} & set(out)


def test_with_models(monkeypatch, tmp_path):
    class Model:
        def predict(self, X):
            return [0.01 + 0.001 * row[1] + 0.05 * row[len(ranker2.FEATURES)] for row in X]  # carted_today lifts
    paths = [tmp_path / "click.txt", tmp_path / "buy.txt"]
    for p in paths:
        p.write_text("stub")
    monkeypatch.setattr(ranker3, "MODEL", paths[0])
    monkeypatch.setattr(ranker3, "BUY_MODEL", paths[1])
    state, s = State3(), ranker3.Ranker3()
    s.mtimes, s.models = tuple(p.stat().st_mtime for p in paths), (Model(), Model())
    for views, user in ((["p1", "p4", "p7"], "known"), ([], "known"), ([], "nobody"), (["zzz"], "nobody")):
        out = s.recommend(request(views, user), state)
        assert len(out) == len(set(out)) == 10
        assert all(state.available(p) for p in out) and not {"p3", "p9"} & set(out)
    assert s.recommend(request(["p1"]), state)[0] == "p55"
