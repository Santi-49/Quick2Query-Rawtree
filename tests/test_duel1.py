from q2q.strategies import duel1
from q2q.strategy import Request

A = [f"a{i}" for i in range(10)]
B = [f"b{i}" for i in range(10)]


def check(out, ca, cb):
    assert len(out) == len(set(out))
    assert not set(ca) & set(cb)
    assert sorted(ca + cb) == sorted(out)


def test_disjoint_lists_split_five_five():
    out, ca, cb = duel1.interleave("r_1", A, B)
    check(out, ca, cb)
    assert len(out) == 10 and len(ca) == len(cb) == 5
    assert ca == A[:5] and cb == B[:5]


def test_balanced_over_many_requests():
    first_a = 0
    slot_a = [0] * 10
    n = 4000
    for i in range(n):
        out, ca, cb = duel1.interleave(f"r_{i:x}", A, B)
        first_a += out[0] in ca
        for k, pid in enumerate(out):
            slot_a[k] += pid in ca
    assert abs(first_a / n - 0.5) < 0.03
    assert all(abs(s / n - 0.5) < 0.03 for s in slot_a)


def test_deterministic_per_request():
    assert duel1.interleave("r_abc", A, B) == duel1.interleave("r_abc", A, B)
    outs = {tuple(duel1.interleave(f"r_{i}", A, B)[0]) for i in range(50)}
    assert len(outs) > 1


def test_heavy_overlap():
    b = ["a1", "a0", "a2", "a3", "x1", "a4", "x2", "a5", "x3", "x4"]
    for i in range(200):
        out, ca, cb = duel1.interleave(f"r_{i}", A, b)
        check(out, ca, cb)
        assert len(out) == 10 and len(ca) == len(cb) == 5


def test_identical_lists():
    for i in range(100):
        out, ca, cb = duel1.interleave(f"r_{i}", A, list(A))
        check(out, ca, cb)
        assert out == A and len(ca) == len(cb) == 5


def test_short_and_empty_lists():
    out, ca, cb = duel1.interleave("r_s", A, B[:2])
    check(out, ca, cb)
    assert len(out) == 10 and cb == B[:2] and len(ca) == 8
    out, ca, cb = duel1.interleave("r_e", [], B)
    check(out, ca, cb)
    assert out == B and ca == []
    assert duel1.interleave("r_n", [], []) == ([], [], [])


class Fixed:
    def __init__(self, items):
        self.items = items

    def recommend(self, req, state):
        return self.items


def test_recommend_logs_credit(monkeypatch):
    monkeypatch.setattr(duel1, "SOURCES", {"ranker2": Fixed(A), "blend1": Fixed(B)})
    monkeypatch.setattr(duel1, "_started", True)   # no flush thread, nothing leaves the process
    monkeypatch.setattr(duel1, "BUF", [])
    req = Request("r_x", 1763130000.0, "u", False, "home", "web", "ES", [])
    out = duel1.STRATEGY.recommend(req, None)
    row = duel1.BUF[-1]
    assert row["kind"] == "duel" and row["request_id"] == "r_x" and (row["a"], row["b"]) == ("ranker2", "blend1")
    assert sorted(row["a_items"] + row["b_items"]) == sorted(out)
    assert row["ts"] == "2025-11-14 14:20:00.000"
