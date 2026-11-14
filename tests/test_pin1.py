from test_cold2 import FakeState, check, request

from q2q.strategies import pin1, ranker2


def test_today_carts_lead_then_ranker2(monkeypatch):
    state = FakeState()
    base = [f"p{i}" for i in range(20, 30)]
    monkeypatch.setattr(ranker2.STRATEGY, "recommend", lambda req, st: list(base))
    carts = {"known": {"p0": 5, "p1": 4, "p25": 1, "p40": 2, "p41": 1, "p42": 1, "zz": 9}}
    state.today_carts = lambda u: carts.get(u, {})
    items = pin1.STRATEGY.recommend(request("known"), state)
    check(items, state, state.shoppers["known"].bought)
    assert items[:3] == ["p40", "p25", "p41"]   # p0 bought, p1 unavailable, zz unknown; ties in ranker2's order, then by id
    assert items[3:] == [p for p in base if p != "p25"][:7]
    assert pin1.STRATEGY.recommend(request("nobody"), state) == base
