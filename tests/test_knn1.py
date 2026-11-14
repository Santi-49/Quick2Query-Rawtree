import time

import pytest

from q2q.strategies import knn1
from q2q.strategy import Request

BASE = [f"b{i}" for i in range(10)]


class Base:
    def recommend(self, req, state):
        return list(BASE)


@pytest.fixture(autouse=True)
def fake_ranker2(monkeypatch):
    monkeypatch.setattr(knn1.ranker2, "STRATEGY", Base())


def request(views=("p1", "p2")):
    return Request("r", 1200.0, "u1", False, "product", "web", "ES", list(views))


def test_fusion_order(monkeypatch):
    monkeypatch.setattr(knn1, "neighbours", lambda views, user, as_of=None: ["b3", "n1", "n2"])
    monkeypatch.setattr(knn1, "WEIGHT", 0.6)
    monkeypatch.setattr(knn1, "K", 10.0)
    top = knn1.Knn1().recommend(request(), None)
    # b3: 1/13 + 0.6/10; n1: 0.6/11 = 0.0545 sits between b8 (1/18) and b9 (1/19); n2: 0.6/12 is cut
    assert top == ["b3", "b0", "b1", "b2", "b4", "b5", "b6", "b7", "b8", "n1"]


def test_fallback_on_timeout(monkeypatch):
    monkeypatch.setattr(knn1, "neighbours", lambda views, user, as_of=None: time.sleep(knn1.TIMEOUT + 0.5) or ["n1"])
    t = time.monotonic()
    assert knn1.Knn1().recommend(request(), None) == BASE
    assert time.monotonic() - t < knn1.TIMEOUT + 0.3


def test_fallback_on_error_and_empty(monkeypatch):
    def boom(views, user, as_of=None):
        raise RuntimeError("HTTP 500")
    monkeypatch.setattr(knn1, "neighbours", boom)
    assert knn1.Knn1().recommend(request(), None) == BASE
    monkeypatch.setattr(knn1, "neighbours", lambda views, user, as_of=None: [])
    assert knn1.Knn1().recommend(request(), None) == BASE
    assert knn1.Knn1().recommend(request(()), None) == BASE


def test_as_of_in_sql():
    q = knn1.sql(["p1", "p2", "p1"], "u1", as_of=1200.0)
    assert "toDateTime64(1200.000, 3)" in q and "now64" not in q
    assert "['p2','p1'], [1.000,2.000]" in q    # a repeat counts at its newest position
    assert "now64(3)" in knn1.sql(["p1"], "u1")
