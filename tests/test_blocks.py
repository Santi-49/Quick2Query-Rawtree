"""Offline checks of the block recursion on synthetic leaderboards with known block lifts."""
import os
import random

os.environ.setdefault("TEAM_ID", "team_x")
from q2q import evaluate as ev  # noqa: E402

US = "team_x"
START_SLOT = 2_950_000
N = 30  # blocks after start


def truth() -> dict[int, float]:
    """True lift per block: 0 up to START_SLOT, random after."""
    rng = random.Random(1)
    return {s: (0.0 if s <= START_SLOT else rng.uniform(-2, 2)) for s in range(START_SLOT - 10, START_SLOT + N + 1)}


def windows(lift: dict[int, float]) -> dict[int, float]:
    """D per refresh: the sum of the six block lifts in its hour."""
    return {s: sum(lift[k] for k in range(s - 5, s + 1)) for s in range(START_SLOT - 4, START_SLOT + N + 1)}


def rows(d: dict[int, float], jitter=lambda s: 0) -> list[dict]:
    """Leaderboard rows that produce D: baseline at 1.0 conversion, us shifted by D (requests = 100)."""
    out = []
    for s, v in d.items():
        end = ev.iso(ev.slot_time(s) + jitter(s))
        out.append({"window_end": end, "team_id": "baseline", "conv": 1.0, "reqs": 100.0})
        out.append({"window_end": end, "team_id": US, "conv": 1.0 + v, "reqs": 100.0})
    return out


def recover(rs: list[dict]) -> dict[int, float | None]:
    picked = ev.pick(rs, US)
    d = {s: ev.purchases(t[US]) - ev.purchases(t["baseline"]) for s, t in picked.items()}
    return ev.lifts(d, START_SLOT, START_SLOT + N)


def test_recovers_exact_lifts():
    lift = truth()
    got = recover(rows(windows(lift), jitter=lambda s: random.Random(s).randint(-3, 3)))
    for s, v in got.items():
        assert abs(v - lift[s]) < 1e-9


def test_missing_refresh_poisons_dependents_only():
    lift = truth()
    d = windows(lift)
    gone = START_SLOT + 10
    del d[gone]
    got = recover(rows(d))
    # unknown: the block entering at the missing refresh, the one after it, and every block 6, 12, ... later
    bad = {s for s in got if (s - gone) % 6 in (0, 1) and s >= gone}
    for s, v in got.items():
        if s in bad:
            assert v is None, s
        else:
            assert abs(v - lift[s]) < 1e-9, s


def test_duplicates_do_not_change_result():
    lift = truth()
    rs = rows(windows(lift))
    base = recover(rs)
    # exact copies, plus a minute-later refresh with other content: the one closest to the slot wins
    late = rows({START_SLOT + 5: 99.0}, jitter=lambda s: 40)
    assert recover(rs + rs[::3] + late) == base
