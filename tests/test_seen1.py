from test_cold2 import FakeState, check, request

from q2q.strategies import ranker2, seen1


def test_last_views_lead_then_ranker2(monkeypatch):
    state = FakeState()
    base = [f"p{i}" for i in range(20, 30)]
    monkeypatch.setattr(ranker2.STRATEGY, "recommend", lambda req, st: list(base))
    req = request("known")
    req.views = ["p40", "p25", "p0", "p1", "zz", "p41"]   # p0 bought, p1 unavailable, zz unknown
    items = seen1.STRATEGY.recommend(req, state)
    check(items, state, state.shoppers["known"].bought)
    assert items[:2] == ["p41", "p25"]
    assert items[2:] == [p for p in base if p != "p25"][:8]
