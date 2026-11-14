"""Our lift over the baseline per 10-minute block, read off the hourly leaderboard.

    blocks()              -> one dict per block since START
    by_arm(blocks())      -> per model_version: blocks, mean score, standard error, click rate
    report(write=True)    -> print the last 18 blocks and the per-arm summary, log new blocks to scratch

Consecutive hourly windows differ by one block entering and one leaving, so with
D(t) = S_us(t) - S_baseline(t) and S = conversion * requests / 100:
    L(t) = D(t) - D(t - 10 min) + L(t - 60 min),   L = 0 for blocks ending at or before START.
"""
import math
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone

import requests

from q2q import rt
from q2q.strategy import decode, route_of

START = "2026-11-14 13:26:35"  # until then we served the baseline list
STATE_URL = "https://datathon.rawtree.dev/api/state"
ORACLE_GAP = 2.95  # oracle minus baseline, in conversion points
OFFSET, BLOCK = 395, 600  # refreshes land 395 s past each 600 s epoch boundary
MAX_JITTER = 90  # a refresh further than this from its slot time does not count
HOUR = 6  # blocks per leaderboard window


def epoch(s: str) -> float:
    return datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).timestamp()


def iso(e: float) -> str:
    return datetime.fromtimestamp(e, timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def slot_of(e: float) -> int:
    return round((e - OFFSET) / BLOCK)


def slot_time(slot: int) -> float:
    return slot * BLOCK + OFFSET


def pick(rows: list[dict], us: str) -> dict[int, dict]:
    """Leaderboard rows -> slot -> {team_id: row} from the refresh closest to the slot time.

    Duplicate rows for one refresh collapse; refreshes lacking us or the baseline are skipped."""
    by_end = defaultdict(dict)
    for r in rows:
        by_end[r["window_end"][:19]][r["team_id"]] = r
    best = {}
    for end, teams in by_end.items():
        if us not in teams or "baseline" not in teams:
            continue
        e = epoch(end)
        s = slot_of(e)
        off = abs(e - slot_time(s))
        if off <= MAX_JITTER and (s not in best or off < best[s][0]):
            best[s] = (off, teams)
    return {s: teams for s, (_, teams) in best.items()}


def purchases(row: dict) -> float:
    return row["conv"] * row["reqs"] / 100


def lifts(d: dict[int, float], start_slot: int, end_slot: int, weight: dict[int, float] | None = None) -> dict[int, float | None]:
    """L per slot in (start_slot, end_slot] from D per slot; None where a needed refresh is missing.

    With `weight` (our answered requests per slot), a run of slots with missing refreshes is filled:
    the run's total lift is known from the refreshes around it and is shared out by weight.
    A slot where we answered nothing gets 0, because the fallback shows the baseline list."""
    out: dict[int, float | None] = {}
    prev = lambda s: 0.0 if s - HOUR <= start_slot else out.get(s - HOUR)
    s = start_slot + 1
    while s <= end_slot:
        if s in d and s - 1 in d:
            out[s] = None if prev(s) is None else d[s] - d[s - 1] + prev(s)
            s += 1
            continue
        b = s
        while b <= end_slot and b not in d:
            b += 1
        run = list(range(s, min(b, end_slot) + 1))
        total = sum(weight.get(x, 0) for x in run) if weight else 0
        if b > end_slot or s - 1 not in d or not total or any(prev(x) is None for x in run):
            out.update({x: None for x in run})
        else:
            gain = d[b] - d[s - 1] + sum(prev(x) for x in run)
            out.update({x: gain * weight.get(x, 0) / total for x in run})
        s = run[-1] + 1
    return out


def _sql(name: str, since: str) -> list[dict]:
    text = (rt.ROOT / "sql" / "reports" / f"{name}.sql").read_text(encoding="utf-8")
    return rt.query(text.replace("{SINCE}", since))


def _window_score(teams: dict, team: str) -> float | None:
    if team not in teams:
        return None
    return 100 * (teams[team]["conv"] - teams["baseline"]["conv"]) / ORACLE_GAP


def blocks(start: str = START) -> list[dict]:
    """One dict per block after `start` up to the latest logged refresh."""
    start_slot = math.floor((epoch(start) - OFFSET) / BLOCK)
    since = iso(slot_time(start_slot))
    refreshes = pick(_sql("leaderboard", iso(slot_time(start_slot) - 2 * BLOCK)), rt.TEAM)
    later = [s for s in refreshes if s > start_slot]
    if not later:
        return []
    d = {s: purchases(t[rt.TEAM]) - purchases(t["baseline"]) for s, t in refreshes.items()}
    stats = {r["slot"]: r for r in _sql("blocks", since)}
    lift = lifts(d, start_slot, max(later), {s: r.get("answered", 0) for s, r in stats.items()})
    arms = defaultdict(Counter)
    for r in _sql("arms", since):
        arms[r["slot"]][decode(r["model_version"])] += r["n"]
    out = []
    for s, L in lift.items():
        st = stats.get(s, {})
        n, fed = st.get("requests", 0), st.get("fed", 0)
        arm, arm_n = (arms[s].most_common(1) or [("", 0)])[0]
        lift_pp = 100 * L / n if L is not None and n else None
        teams = refreshes.get(s)
        out.append({
            "block_end": iso(slot_time(s)),
            "arm": arm,
            "arm_share": arm_n / n if n else None,
            "requests": n,
            "answered": st.get("answered", 0) / fed if fed else None,
            "lift": L,
            "lift_pp": lift_pp,
            "score": 100 * lift_pp / ORACLE_GAP if lift_pp is not None else None,
            "click_rate": st.get("clicks", 0) / fed if fed else None,
            "purchase_rate": st.get("purchases", 0) / fed if fed else None,
            "window_score": _window_score(teams, rt.TEAM) if teams else None,
            "ref_window_score": _window_score(teams, "reference") if teams else None,
        })
    return out


def by_arm(rows: list[dict]) -> list[dict]:
    """Per arm over blocks with a known lift: count, mean score, standard error, mean click rate."""
    groups = defaultdict(list)
    for r in rows:
        if r["score"] is not None:
            groups[r["arm"]].append(r)
    out = []
    for arm, rs in sorted(groups.items()):
        scores = [r["score"] for r in rs]
        n, mean = len(scores), sum(scores) / len(scores)
        se = math.sqrt(sum((x - mean) ** 2 for x in scores) / (n - 1) / n) if n > 1 else None
        clicks = [r["click_rate"] for r in rs if r["click_rate"] is not None]
        out.append({"arm": arm, "blocks": n, "score": mean, "se": se,
                    "click_rate": sum(clicks) / len(clicks) if clicks else None})
    return out


def _f(x, spec: str, width: int) -> str:
    return (format(x, spec) if x is not None else "-").rjust(width)


def report(start: str = START, write: bool = False) -> None:
    """Print the last 18 blocks and the per-arm summary; with write=True log new blocks to scratch."""
    rows = blocks(start)
    print(f"{'block_end':19} {'arm':>12} {'share':>6} {'reqs':>5} {'ans':>5} {'lift':>6} "
          f"{'lift_pp':>7} {'score':>6} {'click':>6} {'buy':>6} {'win':>6} {'ref_win':>7}")
    for r in rows[-18:]:
        print(f"{r['block_end']:19} {r['arm'][:12]:>12} {_f(r['arm_share'], '.2f', 6)} {r['requests']:>5} "
              f"{_f(r['answered'], '.2f', 5)} {_f(r['lift'], '+.2f', 6)} {_f(r['lift_pp'], '+.3f', 7)} "
              f"{_f(r['score'], '+.1f', 6)} {_f(r['click_rate'], '.3f', 6)} {_f(r['purchase_rate'], '.4f', 6)} "
              f"{_f(r['window_score'], '+.1f', 6)} {_f(r['ref_window_score'], '+.1f', 7)}")
    print(f"\n{'arm':>12} {'blocks':>6} {'score':>6} {'se':>5} {'click':>6}")
    for a in by_arm(rows):
        print(f"{a['arm'][:12]:>12} {a['blocks']:>6} {_f(a['score'], '+.1f', 6)} {_f(a['se'], '.1f', 5)} "
              f"{_f(a['click_rate'], '.3f', 6)}")
    if write and rows:
        done = {r["ts"][:19] for r in rt.query("SELECT DISTINCT ts::String AS ts FROM {TEAM}.scratch WHERE kind::String = 'block'")}
        new = [{"kind": "block", "ts": r["block_end"], **r} for r in rows if r["block_end"] not in done]
        if new:
            rt.insert("scratch", new)
        print(f"\nwrote {len(new)} new block rows to scratch")


def models(minutes: int = 60, end: float | None = None) -> list[dict]:
    """Our model_versions in one leaderboard window, read directly (the by-model view, windows of 15 to 180 minutes).

    Arms on the same route saw the same kind of requests at the same time, so their conversions compare directly."""
    to = math.floor((end or time.time()) / 300) * 300
    s = requests.get(STATE_URL, params={"by": "model", "from": to - 60 * minutes, "to": to}, timeout=20).json()
    us = next(t for t in s["teams"] if t["team_id"] == rt.TEAM)
    base = s["baseline"]["conversion"]
    out = [{"arm": decode(v["model_version"]), "route": route_of(v["model_version"]) or "main", "label": v["model_version"],
            "requests": v["requests"], "conversion": v["conversion"], "cold_conversion": v.get("cold_conversion"),
            "score": 100 * (v["conversion"] - base) / ORACLE_GAP, "baseline": base, "reference": s["reference"]["conversion"],
            "window_end": iso(s["window"][1])} for v in us.get("versions", [])]
    merged = {}   # one arm can appear under two labels after a rename: add them up
    for r in out:
        m = merged.setdefault((r["arm"], r["route"]), dict(r, requests=0, conversion=0.0))
        if r["requests"] > m["requests"]:
            m["label"], m["cold_conversion"] = r["label"], r["cold_conversion"]
        total = m["requests"] + r["requests"]
        m["conversion"] = (m["conversion"] * m["requests"] + r["conversion"] * r["requests"]) / max(total, 1)
        m["requests"], m["score"] = total, 100 * (m["conversion"] - base) / ORACLE_GAP
    return sorted(merged.values(), key=lambda r: (r["route"], -r["requests"]))


def models_report(minutes: int = 60) -> None:
    rows = models(minutes)
    if rows:
        print(f"window {minutes} min to {rows[0]['window_end']} UTC   baseline {rows[0]['baseline']:.2f}%   reference {rows[0]['reference']:.2f}%")
    print(f"{'route':>12} {'arm':>10} {'label':>10} {'reqs':>6} {'conv %':>7} {'cold %':>7} {'score':>6}")
    for r in rows:
        print(f"{r['route']:>12} {r['arm']:>10} {r['label'][:10]:>10} {r['requests']:>6} {r['conversion']:>7.2f} {_f(r['cold_conversion'], '.2f', 7)} {r['score']:>+6.1f}")
