"""Everything the dashboard reads, and how card statuses are derived. No drawing here.

Sources: RawTree (cached 30 s), the per-model leaderboard (each window at most once per 60 s, finished windows once), arms.toml, strategies.toml, knowledge.toml,
docs/SIMULATOR.md, docs/hypotheses/, sql/hypotheses/ and the strategy files. The files are read on every render,
because other agents edit them while the dashboard runs; a file caught half-written keeps its last good reading.
"""
import ast
import importlib
import math
import re
import time
import tomllib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import streamlit as st

from q2q import evaluate, rt, serve, strategy

ROOT = rt.ROOT
ROUTES = {"main": "ordinary", "new_shopper": "new shopper", "no_views": "no recent views"}
ROUTE_HELP = {"main": "returning shopper with recent views", "new_shopper": "new shopper with recent views", "no_views": "the home page"}
KINDS = {**ROUTES, "all": "all kinds", "mixed": "all kinds, before the split"}  # every kind of request a score can be read on
GROUPS = ("tested", "testing", "next")
SPAN = 10800                      # the longest leaderboard window, in seconds
_good: dict[str, dict] = {}       # last good parse per toml file
_windows: dict[tuple[int, int], list] = {}   # finished leaderboard windows, by (minutes, end time)


_code: dict[str, float] = {}      # file time of the router modules as loaded here


def fresh_code(force: bool = False) -> None:
    """The dashboard outlives edits to the router's code (a new strategy gets its public name in strategy.py).
    Streamlit only reloads files next to app.py, so reload these two when their file changed."""
    for module in (strategy, evaluate):
        t = Path(module.__file__).stat().st_mtime
        if force or _code.get(module.__name__, t) != t:
            try:
                importlib.reload(module)
            except Exception:
                continue
        _code[module.__name__] = t


fresh_code(force=True)


def label(name: str, route: str = "") -> str:
    """Public name of a strategy, the one on the leaderboard."""
    return strategy.label(name, route)


def stamp() -> str:
    return time.strftime("%H:%M:%S", time.gmtime()) + " UTC"


# ---------- RawTree and the leaderboard ----------
@st.cache_data(ttl=30, show_spinner=False)
def q(sql: str) -> pd.DataFrame:
    return pd.DataFrame(rt.query(sql))


def report(name: str) -> pd.DataFrame:
    return q((ROOT / "sql" / "reports" / f"{name}.sql").read_text(encoding="utf-8"))


def _kind(arm: str, version: str) -> str:
    """Kind of request a model_version was scored on. Labels from before the split by kind (15:50 UTC) mix all kinds."""
    if arm == "explore":
        return "all"
    if "-" in version.split("@")[0]:
        return next((r for r, suffix in strategy.ROUTES.items() if suffix and version.split("@")[0].endswith(suffix)), "mixed")
    return "main" if version in strategy.PUBLIC.values() else "mixed"


def _per_route(rows: list[dict]) -> pd.DataFrame:
    """Leaderboard rows -> one row per strategy and kind of request. Several windows or public names add up:
    conversion is purchases over requests, the score is the mean of the window scores weighted by requests."""
    b = pd.DataFrame(rows)
    if b.empty:
        return pd.DataFrame(columns=["arm", "route", "requests", "conversion", "score", "labels", "baseline", "reference", "window_end"])
    b["route"] = [_kind(a, v) for a, v in zip(b.arm, b.label)]
    b["buys"], b["points"] = b.conversion * b.requests, b.score * b.requests
    g = b.groupby(["arm", "route"], as_index=False).agg(requests=("requests", "sum"), buys=("buys", "sum"), points=("points", "sum"),
                                                        labels=("label", lambda x: ", ".join(dict.fromkeys(x))),
                                                        baseline=("baseline", "last"), reference=("reference", "last"), window_end=("window_end", "max"))
    g["conversion"], g["score"] = g.buys / g.requests, g.points / g.requests
    return g


@st.cache_data(ttl=60, show_spinner=False)
def board(minutes: int) -> pd.DataFrame:
    """Per strategy and kind of request in the last `minutes`, straight from the per-model leaderboard."""
    return _per_route(evaluate.models(minutes))


def _window(minutes: int, end: int) -> list[dict]:
    """One finished window, asked for once and kept."""
    if (minutes, end) not in _windows:
        try:
            _windows[minutes, end] = evaluate.models(minutes, end)
        except Exception:
            return []
    return _windows[minutes, end]


@st.cache_data(ttl=60, show_spinner=False)
def history(n: int = 8) -> pd.DataFrame:
    """Score per strategy and kind of request in each of the last n finished 15-minute windows."""
    last = math.floor((time.time() - 60) / 900) * 900
    with ThreadPoolExecutor(4) as pool:
        parts = [_per_route(rows) for rows in pool.map(lambda e: _window(15, e), [last - 900 * k for k in range(n)])]
    for key in [k for k in _windows if k[0] == 15 and k[1] < last - 900 * 24]:
        del _windows[key]
    return pd.concat(parts, ignore_index=True)


@st.cache_data(ttl=300, show_spinner=False)
def whole_run() -> pd.DataFrame:
    """Per strategy and kind of request since we started serving: finished 3-hour windows plus the stretch up to now."""
    now = math.floor(time.time() / 300) * 300
    start = math.floor(evaluate.epoch(evaluate.START) / SPAN) * SPAN
    ends = list(range(start + SPAN, now + 1, SPAN))
    rows = [r for e in ends for r in _window(SPAN // 60, e)]
    tail = (now - (ends[-1] if ends else start)) // 60
    if tail >= 15:
        try:
            rows += evaluate.models(tail, now)
        except Exception:
            pass
    return _per_route(rows)


def live() -> pd.DataFrame:
    """One row per request of the last 5 minutes, with the strategy that answered and the kind of request."""
    df = report("live").copy()
    if df.empty:
        return df
    df["model_version"] = df.model_version.fillna("")
    df["strategy"] = df.model_version.map(lambda m: strategy.decode(m) if m else "")
    df["route"] = [("no_views" if not v else "new_shopper" if n else "main") for v, n in zip(df.views, df.new_shopper)]
    return df


def shares(df: pd.DataFrame) -> dict[str, float]:
    """Share of the last 5 minutes of requests answered by each strategy, in %."""
    if df.empty:
        return {}
    return (100 * df[df.strategy != ""].strategy.value_counts() / len(df)).to_dict()


# ---------- files ----------
def _toml(name: str) -> dict:
    try:
        _good[name] = tomllib.loads((ROOT / name).read_text(encoding="utf-8"))
    except Exception:
        pass
    return _good.get(name, {})


def arms() -> dict:
    fresh_code()
    return {**serve.DEFAULTS, **_toml("arms.toml")}


def registry() -> dict:
    reg = _toml("strategies.toml")
    return {"strategies": reg.get("strategies", {}), "plan": reg.get("plan", []), "backlog": reg.get("backlog", [])}


EVIDENCE = ("live", "reversed live", "early", "history only", "live views only")  # firmest first


def knowledge() -> dict:
    """Factors seen on live purchases or clicks first, then the weaker evidence; inside each, the largest effect first."""
    k = _toml("knowledge.toml")
    firm = lambda f: f.get("evidence") not in EVIDENCE[:2]
    weight = lambda f: abs(math.log(max(float(f.get("size", 1)), 1e-6)))
    return {"factors": sorted(k.get("factor", []), key=lambda f: (firm(f), -weight(f))),
            "no_effect": k.get("no_effect", []), "lessons": k.get("lessons", [])}


def planned(cfg: dict) -> dict[str, dict[str, float]]:
    """Kind of request -> strategy -> the share of that kind arms.toml gives it, in % (the rule of serve.arm_for)."""
    explore = 100 * float(cfg.get("explore_share", 0))
    out = {}
    for route, names in serving(cfg).items():
        out[route] = {n: (100 - explore) / len(names) for n in names}
        if explore:
            out[route]["explore"] = explore
    return out


def observed(df: pd.DataFrame) -> dict[str, dict[str, float]]:
    """Kind of request -> strategy -> share of that kind's requests it answered in the last 5 minutes, in %."""
    out = {}
    for route in ROUTES:
        part = df[df.route == route] if not df.empty else df
        out[route] = (100 * part[part.strategy != ""].strategy.value_counts() / len(part)).to_dict() if len(part) else {}
    return out


def plan_state(when: str) -> str:
    """"16:35–17:35" (UTC, today) -> done, now or next. Anything else is later."""
    m = re.fullmatch(r"\s*(\d{1,2}):(\d{2})\s*[–-]\s*(\d{1,2}):(\d{2})\s*", str(when))
    if not m:
        return "later"
    a, b, c, d = map(int, m.groups())
    t = time.gmtime()
    now, start, end = t.tm_hour * 60 + t.tm_min, a * 60 + b, c * 60 + d
    return "done" if now >= end else "now" if now >= start else "next"


def serving(cfg: dict) -> dict[str, list[str]]:
    """Kind of request -> the strategies arms.toml sends it to (the explore share comes on top, on every kind)."""
    main = list(cfg.get("schedule") or [cfg["champion"]])
    routes = cfg.get("routes") or {}
    return {"main": main, "new_shopper": list(routes.get("new_shopper") or main), "no_views": list(routes.get("no_views") or main)}


def running(cfg: dict) -> set[str]:
    return {a for arms_ in serving(cfg).values() for a in arms_} | ({"explore"} if cfg.get("explore_share", 0) > 0 else set())


def brief(text: str, sentences: int = 2) -> str:
    text = re.sub(r"[*`]", "", " ".join(str(text).split()))
    return " ".join(re.split(r"(?<=[.!?])\s+", text)[:sentences])


def source(name: str) -> str:
    path = ROOT / f"src/q2q/strategies/{name}.py"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _docstring(name: str) -> str:
    try:
        return (ast.get_docstring(ast.parse(source(name))) or "").split("\n\n")[0]
    except SyntaxError:
        return ""


def strategies(cfg: dict, reg: dict) -> list[dict]:
    """Every strategy file and registry entry, with its group.

    testing = arms.toml gives it traffic; tested = status "retired" in strategies.toml; next = anything else
    (status "queued", or a strategy file that is not in the registry yet)."""
    files = sorted(f.stem for f in (ROOT / "src/q2q/strategies").glob("*.py") if f.stem != "__init__")
    live_now, routes = running(cfg), serving(cfg)
    out = []
    for name in dict.fromkeys(files + list(reg["strategies"])):
        info = reg["strategies"].get(name, {})
        group = "testing" if name in live_now else "tested" if info.get("status") == "retired" else "next"
        tag = ("Champion" if name == cfg["champion"] else "Testing now") if group == "testing" else \
              "Tested" if group == "tested" else "Queued" if name in files else "Planned"
        out.append({"name": name, "public": label(name), "group": group, "tag": tag,
                    "summary": info.get("summary") or _docstring(name) or "No description yet.",
                    "conclusion": info.get("conclusion", ""), "hypotheses": list(info.get("hypotheses", [])),
                    "routes": list(ROUTES) if name == "explore" else [r for r, a in routes.items() if name in a],
                    "registered": name in reg["strategies"], "has_file": name in files})
    return out


def simulator_rows() -> dict[str, dict]:
    """slug -> verdict, claim, evidence, consequence, test from the two hypothesis tables of docs/SIMULATOR.md."""
    out = {}
    try:
        text = (ROOT / "docs/SIMULATOR.md").read_text(encoding="utf-8")
    except OSError:
        return out
    for title in ("Verdicts on the first hypotheses", "New hypotheses"):
        if f"## {title}" not in text:
            continue
        for line in text.split(f"## {title}")[1].split("\n## ")[0].splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if not line.startswith("|") or cells[0] in ("Slug", "") or set(cells[0]) <= {"-", " ", ":"}:
                continue
            row = out.setdefault(cells[0], {})
            if len(cells) >= 4:
                row.update(verdict=cells[1].replace("*", ""), evidence=cells[2], consequence=cells[3])
            elif len(cells) == 3:
                row.update(claim=cells[1], test=cells[2])
    return out


def _field(text: str, name: str) -> str:
    m = re.search(rf"^\s*-?\s*\*\*{name}\*\*:\s*(.+)$", text, re.M | re.I)
    return m.group(1).strip() if m else ""


def kind_of(verdict: str) -> str:
    """Verdict text -> one of confirmed, mixed, rejected, open. Drives the tag's label and shape."""
    v = verdict.lower().lstrip("* ")
    if not v or re.match(r"open|in test|pending|running|not tested", v):
        return "open"
    if re.match(r"rejected in part|confirmed in part|likely|weak|answered|partly|mixed", v):
        return "mixed"
    if re.match(r"rejected|refuted", v):
        return "rejected"
    return "confirmed" if v.startswith("confirmed") else "mixed"


def hypotheses(reg: dict, cfg: dict) -> list[dict]:
    """Every hypothesis we know of, with its group.

    tested = a write-up in docs/hypotheses with a verdict, or a verdict other than "open" in docs/SIMULATOR.md;
    testing = a write-up still open, an "open" verdict, queries without a write-up, or linked from a running strategy;
    next = listed under "New hypotheses" or named by a backlog idea or a queued strategy, and nothing else yet."""
    sim, live_now = simulator_rows(), running(cfg)
    docs = {f.stem[2:]: f for f in (ROOT / "docs/hypotheses").glob("H-*.md")}
    sqls = {f.stem[2:] for f in (ROOT / "sql/hypotheses").glob("H-*.sql")}
    used: dict[str, list[str]] = {}
    for name, info in reg["strategies"].items():
        for slug in info.get("hypotheses", []):
            used.setdefault(slug, []).append(name)
    ideas: dict[str, list[str]] = {}
    for b in reg["backlog"]:
        if b.get("hypothesis"):
            ideas.setdefault(b["hypothesis"], []).append(b.get("idea", ""))
    out = []
    for slug in dict.fromkeys(list(docs) + list(sim) + sorted(sqls) + list(used) + list(ideas)):
        row = dict(sim.get(slug, {}))
        text = docs[slug].read_text(encoding="utf-8") if slug in docs else ""
        title = text.splitlines()[0].split("·", 1)[-1].strip() if text.startswith("#") and "·" in text.splitlines()[0] else ""
        verdict = _field(text, "status") or row.get("verdict", "")
        kind = kind_of(verdict)
        if kind != "open":
            group = "tested"
        elif text or row.get("verdict") or slug in sqls or any(n in live_now for n in used.get(slug, [])):
            group = "testing"
        else:
            group = "next"
        out.append({"slug": slug, "title": title, "group": group, "kind": kind, "verdict": verdict,
                    "claim": _field(text, "claim") or row.get("claim", ""), "evidence": row.get("evidence", ""),
                    "consequence": row.get("consequence", ""), "test": _field(text, "test") or row.get("test", ""),
                    "text": text, "has_sql": slug in sqls, "used_by": used.get(slug, []), "ideas": ideas.get(slug, [])})
    order = lambda h: (not h["text"], -len(h["used_by"]), not h["has_sql"])
    return sorted(out, key=order)


def statements(slug: str) -> list[tuple[str, str]]:
    """(title, sql) for each query of sql/hypotheses/H-<slug>.sql."""
    path = ROOT / f"sql/hypotheses/H-{slug}.sql"
    if not path.exists():
        return []
    parts = [s.strip() for s in path.read_text(encoding="utf-8").split(";\n")]
    parts = [s for s in parts if s and not all(l.startswith("--") for l in s.splitlines())]
    return [(next((l.lstrip("- ") for l in reversed(s.splitlines()) if l.startswith("--")), s[:50]), s) for s in parts]
