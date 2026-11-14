from q2q.strategy import N, guard


class FakeState:
    def __init__(self, best, unavailable=()):
        self.best, self.unavailable = best, set(unavailable)

    def available(self, pid):
        return pid not in self.unavailable


def test_drops_unavailable_and_duplicates_and_pads():
    state = FakeState([f"b{i}" for i in range(20)], unavailable={"x", "b0"})
    out = guard(["a", "x", "a", "b1"], state)
    assert out == ["a", "b1", "b2", "b3", "b4", "b5", "b6", "b7", "b8", "b9"]


def test_never_returns_unavailable():
    best = [f"b{i}" for i in range(30)]
    state = FakeState(best, unavailable=set(best[::2]))
    out = guard(best[:12], state)
    assert len(out) == N and len(set(out)) == N
    assert all(state.available(p) for p in out)


def test_short_only_when_too_few_available():
    state = FakeState(["b0", "b1", "b2"], unavailable={"b1"})
    assert guard(["a", "b1"], state) == ["a", "b0", "b2"]
