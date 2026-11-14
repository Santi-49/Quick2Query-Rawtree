from datetime import datetime, timezone

from q2q.strategy import decode
from q2q import serve
from q2q.strategy import N, Request

CFG = {"champion": "baseline", "schedule": [], "explore_share": 0.03, "salt": "q2q-1", "routes": {}}


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


def test_arms_split_shoppers_evenly_and_stably():
    cfg = {**CFG, "explore_share": 0.0, "schedule": ["a", "b"]}
    arms = [serve.arm_for(req(user=f"u{i}"), cfg) for i in range(20000)]
    assert 0.48 < arms.count("a") / len(arms) < 0.52
    assert serve.arm_for(req(user="u7"), cfg) == serve.arm_for(req(user="u7", ts=1794669999.0), cfg)


def test_answer_guards_and_labels():
    items, mv = serve.answer(req(), {**CFG, "explore_share": 0}, FakeState(), lambda n: Named(n), "abc")
    assert decode(mv) == "baseline" and items[:2] == ["a", "b0"] and len(items) == N and "b3" not in items


def test_failing_strategy_gives_baseline():
    cfg = {**CFG, "explore_share": 0, "champion": "rules"}
    items, mv = serve.answer(req(), cfg, FakeState(), lambda n: Named(n, fail=True), "abc")
    assert decode(mv) == "baseline"
    assert items == [p for p in FakeState.best if p != "b3"][:N]


def test_cold_routes_take_requests_before_the_schedule():
    cfg = {**CFG, "explore_share": 0.0, "schedule": ["x"], "routes": {"no_views": ["h1", "h2"], "new_shopper": []}}
    home, new = req(), req()
    new.views, new.is_new_user = ["p"], True
    assert serve.arm_for(home, cfg) in ("h1", "h2")
    assert serve.arm_for(new, cfg) == "x"
    assert {serve.arm_for(req(user=f"u{i}"), cfg) for i in range(50)} == {"h1", "h2"}
