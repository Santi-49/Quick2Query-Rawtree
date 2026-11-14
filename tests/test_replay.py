import math

import numpy as np
import pandas as pd

from q2q.replay import as_of, indicators, prepare, summarize


def reqs():
    """Three requests: a purchase on main, an organic purchase on home, nothing on new_shopper."""
    shown = [f"p{i}" for i in range(10)]
    return pd.DataFrame([
        {"rid": "a", "t": 100.0, "u": "u1", "new": False, "page": "product", "dev": "web", "reg": "X", "vp": ["p3"],
         "shown": shown, "clicked": "p3", "purchased": "p3", "served": "team", "mv": "onyx"},          # rules4
        {"rid": "b", "t": 200.0, "u": "u2", "new": False, "page": "home", "dev": "web", "reg": "X", "vp": [],
         "shown": shown, "clicked": "", "purchased": "", "served": "fallback", "mv": ""},              # baseline
        {"rid": "c", "t": 300.0, "u": "u3", "new": True, "page": "product", "dev": "web", "reg": "X", "vp": ["p1"],
         "shown": shown, "clicked": "", "purchased": "", "served": "team", "mv": "shale"},             # ranker2
    ])


def frames():
    buys = pd.DataFrame([{"u": "u2", "p": "q9", "t": 500.0, "organic": True},      # 300 s after b, not shown
                         {"u": "u2", "p": "p1", "t": 600.0, "organic": True},      # shown: not organic
                         {"u": "u1", "p": "p3", "t": 101.0, "organic": False},     # our own sale
                         {"u": "u9", "p": "z", "t": 5000.0, "organic": True}])     # so every window is complete
    today = pd.DataFrame([{"u": "u1", "p": "p5", "cart": 0, "t": 50.0}, {"u": "u1", "p": "p6", "cart": 1, "t": 60.0},
                          {"u": "u1", "p": "p5", "cart": 0, "t": 150.0}])
    return {"reqs": reqs(), "buys": buys, "today": today, "meta": pd.DataFrame([{"start": "x", "end": "y"}])}


def test_prepare_routes_logger_organic():
    r, shares, buys, today = prepare(frames(), n_organic=10, n_sample=3)
    assert list(r["route"]) == ["main", "no_views", "new_shopper"]
    assert list(r["logger"]) == ["rules4", "baseline", "ranker2"]
    assert list(r["organic"]) == [[], ["q9"], []]
    assert math.isclose(sum(shares.values()), 1.0)


def test_as_of_uses_only_the_past():
    _, _, buys, today = prepare(frames(), 10, 3)

    class S:
        _live, _today, _today_carts = {}, {}, {}
    s = S()
    as_of(s, "u1", 100.0, buys, today)
    assert s._live["u1"] == set() and s._today["u1"] == ["p5"] and s._today_carts["u1"] == {"p6": 1}
    as_of(s, "u1", 200.0, buys, today)
    assert s._live["u1"] == {"p3"}


def test_indicators():
    r, *_ = prepare(frames(), 10, 3)
    tops = [["x", "x2", "p3"] + [f"y{i}" for i in range(7)], ["q9"] + [f"y{i}" for i in range(9)], [f"p{i}" for i in range(10)]]
    ind = indicators("rules4", r, tops)
    assert ind.loc[0, "hit1"] == 0 and ind.loc[0, "hit3"] == 1 and ind.loc[0, "hit10"] == 1
    assert math.isnan(ind.loc[0, "hit10_other"])            # rules4 logged it
    assert indicators("ranker2", r, tops).loc[0, "hit10_other"] == 1
    assert ind.loc[1, "organic10"] == 1 and math.isnan(ind.loc[0, "organic10"])
    assert ind.loc[0, "overlap"] == 0.1 and ind.loc[2, "overlap"] == 1.0
    assert math.isnan(ind.loc[2, "hit1"])


def test_summarize_weights_routes_by_share():
    ind = pd.DataFrame({"route": ["main"] * 4 + ["no_views"] * 2, "hit1": [1, 1, 0, 0, 1, 1]})
    for m in ["hit3", "hit10", "hit10_other", "organic10", "overlap"]:
        ind[m] = np.nan
    s = summarize(ind, {"main": 0.75, "no_views": 0.25, "new_shopper": 0.0})
    assert s["hit1"]["main"][0] == 0.5 and s["hit1"]["main"][2] == 4
    assert math.isclose(s["hit1"]["all"][0], 0.75 * 0.5 + 0.25 * 1.0)
    assert s["hit1"]["no_views"][1] == 0.0 and s["hit1"]["main"][1] > 0
    assert s["hit3"]["all"][2] == 0
