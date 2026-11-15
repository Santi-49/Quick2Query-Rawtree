from test_cold2 import FakeState, request

from q2q.strategies import lock1, ranker2


def test_without_views_answers_like_ranker2(monkeypatch):
    base = [f"p{i}" for i in range(20, 30)]
    monkeypatch.setattr(ranker2.STRATEGY, "recommend", lambda req, st: list(base))
    monkeypatch.setattr(ranker2, "context", lambda req, st: {"views": []})
    assert lock1.STRATEGY.recommend(request("known"), FakeState()) == base
