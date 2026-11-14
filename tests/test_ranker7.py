from q2q import train7
from q2q.strategies import ranker2, ranker7
from test_ranker2 import FakeState, request

END = 10_000


def labels(events, negatives=True):
    return {(p, label): (req.views, today, ms) for req, today, p, label, ms in train7.examples("u", False, "web", "ES", events, END, negatives)}


def test_examples():
    events = [(1, "view", "a", "s1"), (2, "view", "b", "s1"), (3, "view", "a", "s1"), (4, "purchase", "a", "s1"),
              (5, "view", "a", "s2"), (6, "view", "c", "s2"), (END + 1, "view", "d", "s2"), (END + 2, "purchase", "c", "s2")]
    out = labels(events)
    assert set(out) == {("a", 1), ("b", 0), ("c", 1)}  # a bought: later view ignored; d viewed in the unknown tail
    assert out[("a", 1)] == (["a", "b"], ["a", "b"], 3)  # the last view before the purchase, earlier views only
    assert out[("c", 1)] == (["a"], ["b", "a"], 6)  # recent views from session s2 only; today's views newest last
    assert set(labels(events, negatives=False)) == {("a", 1), ("c", 1)}


def test_purchase_without_view_is_no_row():
    assert labels([(1, "purchase", "a", "s1"), (2, "view", "a", "s1")]) == {}


def test_fallback_and_blend(monkeypatch, tmp_path):
    monkeypatch.setattr(ranker7, "BUY_MODEL", tmp_path / "none.txt")
    monkeypatch.setattr(ranker2, "MODEL", tmp_path / "none2.txt")
    state = FakeState()
    out = ranker7.Ranker7().recommend(request(["p1", "p4"]), state)
    assert len(out) == len(set(out)) == 10 and "p0" not in out

    class Model:
        def __init__(self, col, sign=1):
            self.col, self.sign = col, sign

        def predict(self, X, num_threads=1):
            return 0.5 + self.sign * 0.001 * X[:, self.col]
    paths = [tmp_path / n for n in ("c.txt", "b.txt", "o.txt")]
    for p in paths:
        p.write_text("stub")
    monkeypatch.setattr(ranker2, "MODEL", paths[0])
    monkeypatch.setattr(ranker2, "BUY_MODEL", paths[1])
    monkeypatch.setattr(ranker7, "BUY_MODEL", paths[2])
    price = ranker2.FEATURES.index("price")
    outs = {}
    for alpha in (1.0, 0.5, 0.0):
        s = ranker7.Ranker7(alpha)
        s.mtimes, s.models = tuple(p.stat().st_mtime for p in paths), (Model(1), Model(1), Model(price, -10))
        outs[alpha] = s.recommend(request(["p1", "p4", "p7"]), state)
        assert len(outs[alpha]) == len(set(outs[alpha])) == 10 and not {"p3", "p9"} & set(outs[alpha])
    assert outs[1.0] != outs[0.0]  # the organic model (price here) changes the order; alpha 0 ignores it
