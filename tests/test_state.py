"""Offline checks of stock timing and the appeal, trend and segment maths."""
import math
import time
from datetime import datetime, timezone

import pytest

from q2q.state import BACK_DELAY, Product, State, appeal, new_appeal, segment_from, trend_from


def ts(seconds_ago: float) -> str:
    return datetime.fromtimestamp(time.time() - seconds_ago, timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def row(change: str, when: str, pid: str = "p1", price: float = 10.0) -> dict:
    return {"ts": when, "product_id": pid, "change": change, "category": "C", "subcategory": "S", "brand": "B",
            "price_eur": price, "description": "Has a vintage look.", "is_active": change != "out_of_stock"}


@pytest.fixture
def state() -> State:
    s = State()
    s.products = {"p1": Product("p1", "C", "S", "B", 10.0, (), False, 100, 5, 1.0)}
    s._base_price = {"p1": 10.0}
    return s


def test_out_of_stock_is_immediate(state):
    assert state.available("p1")
    state._apply(row("out_of_stock", ts(0)), time.time())
    assert not state.available("p1")


def test_back_in_stock_waits_60s_from_row_ts(state):
    state._apply(row("out_of_stock", ts(200)), time.time() - 200)
    state._apply(row("back_in_stock", ts(BACK_DELAY - 10)), time.time() - BACK_DELAY + 10)
    assert not state.available("p1")
    state._apply(row("back_in_stock", ts(BACK_DELAY + 10)), time.time() - BACK_DELAY - 10)
    assert state.available("p1")


def test_back_in_stock_waits_60s_from_first_sight(state):
    state._apply(row("out_of_stock", ts(500)), time.time() - 500)
    state._apply(row("back_in_stock", ts(300)), time.time() - 10)  # old row seen only now
    assert not state.available("p1")


def test_rows_apply_once_and_price_cut(state):
    r = row("price_change", ts(0), price=8.0)
    assert state._apply(r, time.time())
    assert not state._apply(r, time.time())
    assert state.price_cut == {"p1": pytest.approx(0.8)}
    state._apply(row("price_change", ts(-1), price=12.0), time.time())
    assert state.price_cut == {} and state.products["p1"].price == 12.0


def test_new_product(state):
    state._apply(row("new_product", ts(0), pid="p2"), time.time())
    assert state.available("p2") and state.new_products == ["p2"] and state.products["p2"].is_new
    assert state.products["p2"].phrases == ("vintage look",)
    assert state.products["p2"].appeal == pytest.approx(new_appeal(0.0, 0.0))  # empty model predicts 0, 0
    assert not state.available("unknown")


def test_appeal_maths():
    assert appeal(0, 0, math.log(0.04)) == pytest.approx(1 * 0.04 ** 0.5)
    v, b, pb = 1000, 30, math.log(0.02)
    assert appeal(v, b, pb) == pytest.approx(1001 ** 0.2 * ((30 + 50 * 0.02) / 1050) ** 0.5)
    assert new_appeal(math.log(99), math.log(0.04)) == pytest.approx(100 ** 0.2 * 0.2 * 1.2)


def test_trend_maths():
    sub_of = {"a": "A", "b": "B", "c": "C"}
    rows = [{"p": "a", "v15": 400, "v120": 1000}, {"p": "b", "v15": 100, "v120": 1000}, {"p": "c", "v15": 0, "v120": 0}]
    t = trend_from(rows, sub_of)
    assert set(t) == {"A", "B"}
    assert t["A"] == pytest.approx((400 + 20 * 0.5) / 520 / 0.5)
    assert t["B"] == pytest.approx(0.7)  # (100 + 10) / 520 / 0.5 = 0.42, clipped
    assert trend_from([{"p": "a", "v15": 499, "v120": 1000}], sub_of) is None


def test_segment_maths():
    rows = [{"device": "ios", "region": "X", "category": "C", "requests": 100, "buys": 10},
            {"device": "web", "region": "X", "category": "C", "requests": 900, "buys": 10}]
    seg = segment_from(rows)
    assert seg[("ios", "X")]["C"] == pytest.approx(15 / (100 * 0.02 + 5))
    assert seg[("web", "X")]["C"] == pytest.approx(max(0.3, 15 / (900 * 0.02 + 5)))
