import math

import pytest

from q2q.state import Product, Shopper
from q2q.strategies import ranker2
from q2q.strategy import Request

PHRASES = ["sporty style", "luxury feel", "vintage look"]


class FakeState:
    def __init__(self):
        self.products = {f"p{i}": Product(f"p{i}", f"c{i % 3}", f"s{i % 6}", f"b{i % 4}", 10.0 + i, (PHRASES[i % 3], PHRASES[(i + 1) % 3]),
                                          False, 100, 5, 1.0 + i / 100) for i in range(60)}
        self.by_category, self.by_subcategory = {}, {}
        for p in sorted(self.products.values(), key=lambda p: -p.appeal):
            self.by_category.setdefault(p.category, []).append(p.id)
            self.by_subcategory.setdefault(p.subcategory, []).append(p.id)
        self.best = list(self.products)
        self.segment, self.trend, self.price_cut = {}, {}, {}
        self.coview = {"p1": {"p10": 5, "p11": 3}, "p4": {"p10": 2}}
        self.today = {"known": ["p20", "p1"]}
        self.shoppers = {"known": Shopper(bought={"p3", "p9"}, viewed={"p5": 2}, cat_share={"c1": 0.5, "c0": 0.5}, carted={"p5": 4},
                                          phrase_share={"sporty style": 0.4, "luxury feel": 0.1}, brand_share={"b2": 0.3},
                                          sub_share={"s4": 0.25}, cat_carts={"c1": 6}, cart_rate=0.2)}

    def available(self, pid):
        return pid in self.products and pid != "p0"

    def shopper(self, user_id, live=True):
        return self.shoppers.get(user_id)

    def today_views(self, user_id):
        return self.today.get(user_id, [])


def request(views, user="known"):
    return Request("r", 0.0, user, False, "product", "web", "ES", list(views))


def named(p, c, req):
    row = ranker2.features(p, 1, req, c)
    assert len(row) == len(ranker2.FEATURES)
    return dict(zip(ranker2.FEATURES, row))


def test_features_on_toy_state():
    state = FakeState()
    req = request(["p1", "p4", "p7"])  # categories c1, c1, c1; phrases (luxury, vintage) x3
    c = ranker2.context(req, state)
    f = named(state.products["p10"], c, req)  # c1, s4, b2, phrases (luxury, vintage)
    assert f["phrase_share"] == pytest.approx(0.1)
    assert f["session_phrase_overlap"] == 4  # 6 matches, capped
    assert f["coview"] == pytest.approx(math.log1p(7))
    assert f["shopper_cart_rate"] == 0.2 and f["cat_carts"] == pytest.approx(math.log1p(6))
    assert f["brand_share"] == 0.3 and f["sub_share"] == 0.25
    assert f["in_main_cat"] and not f["is_first_view"] and not f["is_later_view"]
    assert not f["viewed_today"]
    first, later = named(state.products["p1"], c, req), named(state.products["p7"], c, req)
    assert first["is_first_view"] and not first["is_later_view"] and later["is_later_view"]
    assert first["session_phrase_overlap"] == 4 and first["viewed_today"] == 0  # own views left out of today's
    assert named(state.products["p5"], c, req)["carted_not_bought"] == 3
    today = named(state.products["p20"], c, req)
    assert today["viewed_today"] and today["sub_viewed_today"]  # p20 is s2, as p20 itself
    new = ranker2.context(request(["p2"], user="nobody"), state)
    g = named(state.products["p10"], new, request(["p2"], user="nobody"))
    assert math.isnan(g["phrase_share"]) and math.isnan(g["brand_share"]) and g["carted_not_bought"] == 0
    assert not g["is_first_view"]  # one view only


def test_fallback_without_model(monkeypatch, tmp_path):
    monkeypatch.setattr(ranker2, "MODEL", tmp_path / "none.txt")
    out = ranker2.Ranker2().recommend(request(["p1", "p4"]), FakeState())
    assert len(out) == len(set(out)) == 10 and "p0" not in out and not {"p3", "p9"} & set(out)


def test_with_models(monkeypatch, tmp_path):
    class Model:
        def predict(self, X):
            return [0.01 + 0.001 * row[1] + 0.01 * row[-4] for row in X]
    paths = [tmp_path / "click.txt", tmp_path / "buy.txt"]
    for p in paths:
        p.write_text("stub")
    monkeypatch.setattr(ranker2, "MODEL", paths[0])
    monkeypatch.setattr(ranker2, "BUY_MODEL", paths[1])
    state, s = FakeState(), ranker2.Ranker2()
    s.mtimes, s.models = tuple(p.stat().st_mtime for p in paths), (Model(), Model())  # loaded already: no reload of the stubs
    for views, user in ((["p1", "p4", "p7"], "known"), ([], "known"), ([], "nobody"), (["zzz"], "nobody")):
        out = s.recommend(request(views, user), state)
        assert len(out) == len(set(out)) == 10
        assert all(state.available(p) for p in out) and not {"p3", "p9"} & set(out)
