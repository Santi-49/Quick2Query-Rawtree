"""Router: poll shop.requests, pick an arm per request, answer within 3 s.

arms.toml is the only deploy switch; it and the strategy files are hot-reloaded.
"""
import hashlib
import os
import socket
import subprocess
import sys
import threading
import time
import tomllib
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from q2q import rt, strategies
from q2q.strategy import Request, decode, guard, label, load

ARMS = rt.ROOT / "arms.toml"
DEFAULTS = {"champion": "baseline", "schedule": [], "explore_share": 0.03, "salt": "q2q-1"}
STALE = 2.7          # seconds: older requests are skipped, the fallback answers them anyway
BLOCK_START = 395    # leaderboard blocks start at minute x6, second 35
POLL = """
SELECT request_id::String AS request_id, user_id::String AS user_id, is_new_user::Bool AS is_new_user,
       context.page::String AS page, context.device::String AS device, context.region::String AS region,
       toUnixTimestamp64Milli(ts::DateTime64(3, 'UTC')) AS ts_ms,
       arrayMap(v -> v.product_id::String, recent_views::Array(JSON)) AS views
FROM shop.requests
ORDER BY ts DESC
LIMIT 60"""
"""Newest 60 requests. recent_views come oldest first (checked live)."""

_said: dict[str, float] = {}
_lock = threading.Lock()
stats = {"answered": 0, "stale": 0, "errors": 0, "arms": Counter(), "compute": [], "latency": []}


def say(msg: str, key: str | None = None, every: float = 10) -> None:
    """Print one line; with a key, at most once per `every` seconds."""
    if key is not None:
        if time.time() - _said.get(key, 0) < every:
            return
        _said[key] = time.time()
    print(msg, flush=True)


def utc(t: float) -> str:
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def bucket(user_id: str, salt: str) -> float:
    """Stable uniform number in [0, 1) per user."""
    return int(hashlib.sha1((user_id + salt).encode()).hexdigest()[:8], 16) / 2**32


def arm_for(req: Request, cfg: dict) -> str:
    if bucket(req.user_id, cfg["salt"]) < cfg["explore_share"]:
        return "explore"
    if cfg["schedule"]:
        return cfg["schedule"][int((req.ts - BLOCK_START) // 600) % len(cfg["schedule"])]
    return cfg["champion"]


def answer(req: Request, cfg: dict, state, get, sha: str) -> tuple[list[str], str]:
    """10 items and the model_version for one request. Never raises."""
    strategy = get(arm_for(req, cfg))
    try:
        return guard(strategy.recommend(req, state), state), label(strategy.name)
    except Exception as e:
        say(f"strategy {strategy.name} failed: {e!r}", key=strategy.name)
        with _lock:
            stats["errors"] += 1
        return guard([], state), label("baseline")


class Arms:
    """arms.toml, re-read when its mtime changes (checked at most once a second)."""

    def __init__(self):
        self.cfg, self.mtime, self.checked = dict(DEFAULTS), None, 0.0

    def get(self) -> tuple[dict, bool]:
        """The config, and whether it changed since the last call."""
        if time.time() - self.checked < 1:
            return self.cfg, False
        self.checked = time.time()
        mtime = ARMS.stat().st_mtime if ARMS.exists() else None
        if mtime == self.mtime:
            return self.cfg, False
        self.mtime = mtime
        try:
            self.cfg = {**DEFAULTS, **(tomllib.loads(ARMS.read_text()) if mtime else {})}
        except Exception as e:
            say(f"arms.toml not loaded, keeping the previous config: {e}")
            return self.cfg, False
        say(f"arms: {self.cfg}")
        return self.cfg, True


class Strategies:
    """Strategy objects by arm name, reloaded when their file changes."""

    def __init__(self):
        self.cache: dict[str, list] = {}  # name -> [strategy, mtime, checked]

    def get(self, name: str):
        path = Path(strategies.__file__).parent / f"{name}.py"
        entry = self.cache.get(name)
        if entry and time.time() - entry[2] < 1:
            return entry[0]
        mtime = path.stat().st_mtime if path.exists() else None
        if entry and mtime == entry[1]:
            entry[2] = time.time()
            return entry[0]
        try:
            strategy = load(name, reload=entry is not None)
        except Exception as e:
            say(f"arm {name} failed to import, using baseline: {e!r}", key=f"import {name}")
            strategy = entry[0] if entry else load("baseline")
        self.cache[name] = [strategy, mtime, time.time()]
        return strategy


def insert(table: str, rows: list[dict]) -> None:
    """rt.insert with one retry."""
    try:
        rt.insert(table, rows)
    except Exception:
        rt.insert(table, rows)


def push(batch: list[tuple[Request, list[str], str]]) -> None:
    """Insert one batch of answers, plus the explore rows into scratch."""
    try:
        insert("submissions", [{"request_id": r.request_id, "items": items, "model_version": mv}
                               for r, items, mv in batch])
    except Exception as e:
        say(f"push failed ({len(batch)} answers): {e}", key="push")
        with _lock:
            stats["errors"] += 1
        return
    now = time.time()
    with _lock:
        for r, _, mv in batch:
            stats["answered"] += 1
            stats["arms"][decode(mv)] += 1
            stats["latency"].append(now - r.ts)
    explore = [{"kind": "explore", "ts": utc(r.ts), "request_id": r.request_id, "user_id": r.user_id,
                "model_version": mv, "items": items, **r.log}
               for r, items, mv in batch if r.log]
    if explore:
        try:
            insert("scratch", explore)
        except Exception as e:
            say(f"explore log failed: {e}", key="explore log")


def report() -> None:
    """One stats line, then reset the window."""
    with _lock:
        lat = sorted(stats["latency"])
        comp = stats["compute"]
        pct = lambda q: lat[min(len(lat) - 1, int(q * len(lat)))] * 1000 if lat else 0
        say(f"answered {stats['answered']} stale {stats['stale']} arms {dict(stats['arms'])} "
            f"compute {sum(comp) / len(comp) if comp else 0:.2f} ms/req "
            f"latency p50 {pct(0.5):.0f} p95 {pct(0.95):.0f} max {lat[-1] * 1000 if lat else 0:.0f} ms "
            f"errors {stats['errors']}")
        stats.update(answered=0, stale=0, errors=0, arms=Counter(), compute=[], latency=[])


def check_lease(host: str) -> None:
    """Exit 3 when another host renewed its lease less than 20 s ago."""
    try:
        rows = rt.query(f"""
            SELECT host::String AS host, ts::String AS ts FROM {{TEAM}}.scratch
            WHERE kind::String = 'lease' AND host::String != '{host}'
            ORDER BY ts::String DESC LIMIT 1""")
    except Exception as e:
        say(f"lease check failed, starting anyway: {e}")
        return
    if rows:
        ts = datetime.fromisoformat(rows[0]["ts"]).replace(tzinfo=timezone.utc).timestamp()
        if time.time() - ts < 20:
            say(f"{rows[0]['host']} holds the lease (renewed {time.time() - ts:.1f} s ago): not starting")
            sys.exit(3)


def run(shadow: bool = False) -> None:
    from q2q.state import State

    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=rt.ROOT, capture_output=True,
                             text=True, check=True).stdout.strip()
    except Exception:
        sha = "nogit"
    host, started = socket.gethostname(), utc(time.time())
    arms, strats = Arms(), Strategies()
    cfg, _ = arms.get()
    state = State()
    state.load()
    if not shadow:
        check_lease(host)
    say(f"serving {'in SHADOW mode ' if shadow else ''}as {host} sha {sha}")

    def refresh():
        while True:
            state.refresh()
            time.sleep(0.5)

    def lease():
        while True:
            try:
                rt.insert("scratch", [{"kind": "lease", "ts": utc(time.time()), "host": host, "pid": os.getpid(),
                                       "started": started, "sha": sha, "champion": arms.cfg["champion"],
                                       "schedule": arms.cfg["schedule"]}])
            except Exception as e:
                say(f"lease write failed: {e}", key="lease")
            time.sleep(5)

    def log_arms(cfg):
        if shadow:
            return
        try:
            rt.insert("scratch", [{"kind": "arms", "ts": utc(time.time()), "champion": cfg["champion"],
                                   "schedule": cfg["schedule"], "explore_share": cfg["explore_share"],
                                   "salt": cfg["salt"], "sha": sha, "host": host}])
        except Exception as e:
            say(f"arms log failed: {e}")

    threading.Thread(target=refresh, daemon=True).start()
    if not shadow:
        threading.Thread(target=lease, daemon=True).start()
    log_arms(cfg)
    pool = ThreadPoolExecutor(4)
    seen: dict[str, None] = {}
    first, reported = True, time.time()
    while True:
        try:
            cfg, changed = arms.get()
            if changed:
                log_arms(cfg)
            fresh = [Request(r["request_id"], float(r["ts_ms"]) / 1000, r["user_id"], bool(r["is_new_user"]),
                             r["page"], r["device"], r["region"], list(r["views"]))
                     for r in reversed(rt.query(POLL)) if r["request_id"] not in seen]
            for r in fresh:
                seen[r.request_id] = None
            for k in list(seen)[:max(0, len(seen) - 5000)]:
                del seen[k]
            if first or not fresh:
                first = False
                time.sleep(0.05)
            else:
                start, batch = time.perf_counter(), []
                for req in fresh:
                    if time.time() - req.ts > STALE:
                        stats["stale"] += 1
                        continue
                    t = time.perf_counter()
                    items, mv = answer(req, cfg, state, strats.get, sha)
                    with _lock:
                        stats["compute"].append((time.perf_counter() - t) * 1000)
                        if shadow:
                            stats["answered"] += 1
                            stats["arms"][decode(mv)] += 1
                            stats["latency"].append(time.time() - req.ts)
                    batch.append((req, items, mv))
                took = (time.perf_counter() - start) * 1000
                if took > 50:
                    say(f"slow batch: {len(fresh)} requests in {took:.0f} ms")
                if batch and not shadow:
                    pool.submit(push, batch)
            if time.time() - reported >= 30:
                reported = time.time()
                report()
        except Exception as e:
            say(f"poll error: {e!r}")
            time.sleep(1)
