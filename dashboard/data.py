"""Everything the dashboard reads, and how card statuses are derived. No drawing here.

Sources: RawTree (cached 20 s), the per-model leaderboard (cached 60 s), arms.toml, strategies.toml, knowledge.toml,
docs/SIMULATOR.md, docs/hypotheses/, sql/hypotheses/ and the strategy files. The files are read on every render,
because other agents edit them while the dashboard runs; a file caught half-written keeps its last good reading.
"""
import ast
import math
import re
import time
import tomllib
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import streamlit as st

from q2q import evaluate, rt, serve
from q2q.strategy import decode, label

ROOT = rt.ROOT
ROUTES = {"main": "ordinary", "new_shopper": "new shopper", "no_views": "no recent views"}
ROUTE_HELP = {"main": "returning shopper with recent views", "new_shopper": "new shopper with recent views", "no_views": "the home page"}
GROUPS = ("tested", "testing", "next")
_good: dict[str, dict] = {}       # last good parse per toml file
_windows: dict[int, list] = {}    # finished 15-minute leaderboard windows, by end time


def stamp() -> str:
    return time.strftime("%H:%M:%S", time.gmtime()) + " UTC"


# ---------- RawTree and the leaderboard ----------
@st.cache_data(ttl=20, show_spinner=False)
def q(sql: str) -> pd.DataFrame:
    return pd.DataFrame(rt.query(sql))


def report(name: str) -> pd.DataFrame:
    return q((ROOT / "sql" / "reports" / f"{name}.sql").read_text(encoding="utf-8"))


def _per_route(rows: list[dict]) -> pd.DataFrame:
    """Leaderboard rows -> one row per strategy and route (a strategy may have had several public names)."""
    b = pd.DataFrame(rows)
    if b.empty:
        return pd.DataFrame(columns=["arm", "route", "requests", "conversion", "score", "labels", "baseline", "reference", "window_end"])
    b["buys"] = b.conversion * b.requests
    g = b.groupby(["arm", "route"], as_index=False).agg(requests=("requests", "sum"), buys=("buys", "sum"), labels=("label", ", ".join),
                                                        baseline=("baseline", "first"), reference=("reference", "first"), window_end=("window_end", "first"))
    g["conversion"] = g.buys / g.requests
    g["score"] = 100 * (g.conversion - g.baseline) / evaluate.ORACLE_GAP
    return g


@st.cache_data(ttl=60, show_spinner=False)
def board(minutes: int) -> pd.DataFrame:
    """Per strategy and route in the last `minutes`, straight from the per-model leaderboard."""
    return _per_route(evaluate.models(minutes))


def _window(end: int) -> list[dict]:
    if end not in _windows:
        try:
            _windows[end] = evaluate.models(15, end)
        except Exception:
            return []
    return _windows[end]


@st.cache_data(ttl=60, show_spinner=False)
def history(n: int = 8) -> pd.DataFrame:
    """Score per strategy and route in each of the last n finished 15-minute windows. Finished windows are kept."""
    last = math.floor(time.time() / 900) * 900
    ends = [last - 900 * k for k in range(n)]
    with ThreadPoolExecutor(4) as pool:
        parts = [_per_route(rows) for rows in pool.map(_window, ends)]
    out = pd.concat(parts, ignore_index=True)
    for e in [e for e in _windows if e < last - 900 * 24]:
        del _windows[e]
    return out


def live() -> pd.DataFrame:
    """One row per request of the last 5 minutes, with the strategy that answered and the kind of request."""
    df = report("live").copy()
    if df.empty:
        return df
    df["model_version"] = df.model_version.fillna("")
    df["strategy"] = df.model_version.map(lambda m: decode(m) if m else "")
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
    return {**serve.DEFAULTS, **_toml("arms.toml")}


def registry() -> dict:
    reg = _toml("strategies.toml")
    return {"strategies": reg.get("strategies", {}), "plan": reg.get("plan", []), "backlog": reg.get("backlog", [])}


def knowledge() -> dict:
    k = _toml("knowledge.toml")
    weight = lambda f: abs(math.log(max(float(f.get("size", 1)), 1e-6)))
    return {"factors": sorted(k.get("factor", []), key=weight, reverse=True), "no_effect": k.get("no_effect", [])}


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
