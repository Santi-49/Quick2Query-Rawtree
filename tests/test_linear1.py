import json

from q2q.strategies import linear1, rules4
from test_ranker2 import FakeState, request


def check(out, state):
    assert len(out) == len(set(out)) == 10
    assert all(state.available(p) for p in out) and not {"p3", "p9"} & set(out)


def test_fallback_without_json(monkeypatch, tmp_path):
    monkeypatch.setattr(linear1, "COEFS", tmp_path / "none.json")
    state, req = FakeState(), request(["p1", "p4"])
    out = linear1.Linear1().recommend(req, state)
    check(out, state)
    assert out == rules4.STRATEGY.recommend(req, state)


def test_with_coefficients(monkeypatch, tmp_path):
    path = tmp_path / "linear1.json"
    n = len(linear1.NAMES)
    click = [0.0] * n
    click[linear1.NAMES.index("in_views")] = 2.0
    click[linear1.NAMES.index("carted")] = 1.5
    path.write_text(json.dumps({"names": linear1.NAMES, "click": click, "click_intercept": -4.0, "buy": [0.1] * n, "buy_intercept": -1.0,
                                "cart_rate_high": 0.1}), encoding="utf-8")
    monkeypatch.setattr(linear1, "COEFS", path)
    state, s = FakeState(), linear1.Linear1()
    state.our_clicks_today = {"known": {"p20"}}
    for views, user in ((["p1", "p4", "p7"], "known"), ([], "known"), ([], "nobody"), (["zzz"], "nobody")):
        out = s.recommend(request(views, user), state)
        check(out, state)
    assert s.recommend(request(["p1", "p4", "p7"]), state)[0] in {"p1", "p4", "p7"}


def test_indicators_length():
    state = FakeState()
    req = request(["p1", "p4"])
    c = linear1.context(req, state)
    row = linear1.indicators(state.products["p5"], 3, req, c)
    assert len(row) == len(linear1.NAMES)
    named = dict(zip(linear1.NAMES, row))
    assert named["slot3"] and named["carted"] and named["carted2"] and named["carted_x_high_cart"] and not named["viewed_only"]
