from test_cold2 import FakeState, check, request

from q2q.strategies import hot1
from q2q.strategies.cold2 import Cold2


def ready_state():
    state = FakeState()
    for s in state.shoppers.values():
        s.carted, s.sub_share = {}, {}
    state.today_views = lambda u: []
    return state


def test_conv_from_shrinks_and_clips():
    rows = [{"p": "a", "v": 1000, "b": 100}, {"p": "b", "v": 1000, "b": 0}, {"p": "c", "v": 50, "b": 1}, {"p": "d", "v": 98000, "b": 900}]
    conv = hot1.conv_from(rows)
    assert conv["a"] == hot1.CLIP and conv["b"] < 0.5
    assert 1 < conv["c"] < 2         # one purchase in 50 views (2%, twice the average): shrunk to near the average
    assert hot1.conv_from([]) == {} and hot1.conv_from([{"p": "a", "v": 5, "b": 0}]) == {}


def test_cold2_list_before_first_load_and_on_error():
    state, s = ready_state(), hot1.Hot1(auto=False)
    assert s.recommend(request("known"), state) == Cold2().recommend(request("known"), state)
    s.conv = {"p2": 2.0}
    s.rank = lambda req, st, conv: 1 / 0
    assert s.recommend(request("known"), state) == Cold2().recommend(request("known"), state)


def test_conv_reorders_and_bought_stays_out():
    state, s = ready_state(), hot1.Hot1(auto=False)
    s.conv = {"p59": 3.0, "p0": 3.0}
    items = s.recommend(request("nobody"), state)
    check(items, state)
    s.conv = {"p32": 3.0}
    assert "p32" in s.recommend(request("nobody"), state)
    s.conv = {"p32": 1 / 3}
    assert "p32" not in s.recommend(request("nobody"), state)
    known = s.recommend(request("known"), state)
    check(known, state, state.shoppers["known"].bought)


def test_bought_subcategory_lifts():
    state, s = ready_state(), hot1.Hot1(auto=False)
    s.conv = {"x": 1.0}
    shopper = state.shoppers["known"]
    shopper.cat_share = {"c0": 0.5, "c1": 0.5}
    shopper.bought = {"p5"}               # subcategory s5 (category c2, never viewed)
    items = s.recommend(request("known"), state)
    check(items, state, shopper.bought)
    plain = Cold2().recommend(request("known"), state)
    assert sum(state.products[p].subcategory == "s5" for p in items) >= sum(state.products[p].subcategory == "s5" for p in plain)
