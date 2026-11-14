from datetime import datetime, timezone

from q2q.strategy import decode
from q2q import serve
from q2q.strategy import N, Request

CFG = {"champion": "baseline", "schedule": [], "explore_share": 0.03, "salt": "q2q-1"}


class FakeState:
    best = [f"b{i}" for i in range(20)]

    def available(self, pid):
        return pid != "b3"


class Named:
    def __init__(self, name, fail=False):
        self.name, self.fail = name, fail

    def recommend(self, req, state):
        if self.fail:
            raise ValueError("boom")
        return ["a", "b3", "a"]


def req(user="u1", ts=1794662462.0):
    return Request("r1", ts, user, False, "home", "web", "ES", [])


def epoch(text):
    return datetime.fromisoformat(text).replace(tzinfo=timezone.utc).timestamp()


def test_explore_share_close_and_stable():
    users = [f"u_{i}" for i in range(20000)]
    explore = [u for u in users if serve.arm_for(req(u), CFG) == "explore"]
    assert abs(len(explore) / len(users) - 0.03) < 0.006
    assert all(serve.arm_for(req(u, ts=0), CFG) == "explore" for u in explore)
    assert serve.arm_for(req("u_1"), {**CFG, "explore_share": 0}) == "baseline"


def test_block_arm_switches_at_x6_35():
    cfg = {**CFG, "explore_share": 0, "schedule": ["rules", "baseline"]}
    boundary = epoch("2026-11-14 13:16:35")
    before = serve.arm_for(req(ts=boundary - 0.01), cfg)
    after = serve.arm_for(req(ts=boundary + 0.01), cfg)
    later = serve.arm_for(req(ts=boundary + 600.01), cfg)
    assert before != after and after != later and {before, after} == {"rules", "baseline"}
    assert serve.arm_for(req(ts=boundary + 599.9), cfg) == after
    assert serve.arm_for(req(ts=epoch("2026-11-14 13:26:34.99")), cfg) == after


def test_answer_guards_and_labels():
    items, mv = serve.answer(req(), {**CFG, "explore_share": 0}, FakeState(), lambda n: Named(n), "abc")
    assert decode(mv) == "baseline" and items[:2] == ["a", "b0"] and len(items) == N and "b3" not in items


def test_failing_strategy_gives_baseline():
    cfg = {**CFG, "explore_share": 0, "champion": "rules"}
    items, mv = serve.answer(req(), cfg, FakeState(), lambda n: Named(n, fail=True), "abc")
    assert decode(mv) == "baseline"
    assert items == [p for p in FakeState.best if p != "b3"][:N]
