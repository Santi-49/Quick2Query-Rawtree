"""The Updates tab: the project's news feed, newest first, and the three newest items on the Now tab.

Stored items come from updates.jsonl (scripts/note.py and the operator append to it), re-read on every refresh.
Result items are computed here, one per finished 30-minute window of the last 3 hours, from the per-model leaderboard.
"""
import calendar
import json
import math
import time
from concurrent.futures import ThreadPoolExecutor
from html import escape

import streamlit as st

import board
import data
import ui

FILE = data.ROOT / "updates.jsonl"
KINDS = {"building": "Building", "live": "Live traffic", "result": "Result", "champion": "New champion",
         "finding": "Finding", "dropped": "Dropped", "ops": "Operations"}
SHOWN = 50


def epoch(ts: str) -> float:
    try:
        return calendar.timegm(time.strptime(ts, "%Y-%m-%dT%H:%M:%SZ"))
    except (TypeError, ValueError):
        return 0.0


def stored() -> list[dict]:
    """Every readable line of updates.jsonl; a line caught half-written is skipped."""
    out = []
    for line in FILE.read_text(encoding="utf-8", errors="replace").splitlines() if FILE.exists() else []:
        try:
            item = json.loads(line)
        except ValueError:
            continue
        if isinstance(item, dict) and item.get("title"):
            out.append(item)
    return out


def window_item(end: int, rows: list[dict]) -> dict | None:
    """One result item for the 30-minute window ending at `end`: the best ordinary model in the title, one line per kind of request."""
    rows = [r for r in rows if r["arm"] != "explore" and r["requests"] >= 100]
    if not rows:
        return None
    name = lambda r: f'{data.label(r["arm"])} ({r["arm"]}) {r["conversion"]:.2f}%, score {r["score"]:+.0f}'
    lines = []
    for route, kind in data.ROUTES.items():
        here = sorted((r for r in rows if r["route"] == route), key=lambda r: -r["score"])
        if here:
            lines.append(f"{kind}: " + " · ".join(f"{name(r)} over {r['requests']:,}" for r in here))
    top = max((r for r in rows if r["route"] == "main"), key=lambda r: r["score"], default=None)
    span = f"{time.strftime('%H:%M', time.gmtime(end - 1800))}–{time.strftime('%H:%M', time.gmtime(end))}"
    best = f"best ordinary model {name(top)}" if top else "no ordinary model with 100 requests"
    return {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(end)), "kind": "result", "title": f"Results {span}: {best}",
            "text": "\n".join(lines), "strategy": top["arm"] if top else ""}


@st.cache_data(ttl=60, show_spinner=False)
def results() -> list[dict]:
    """A result item per finished 30-minute window of the last 3 hours. Each window is read once (data._window keeps it)."""
    last = math.floor((time.time() - 60) / 1800) * 1800
    ends = [e for e in (last - 1800 * k for k in range(6)) if e > data.evaluate.epoch(data.evaluate.START)]
    with ThreadPoolExecutor(3) as pool:
        items = [window_item(e, rows) for e, rows in zip(ends, pool.map(lambda e: data._window(30, e), ends))]
    return [i for i in items if i]


def feed() -> list[dict]:
    """Stored and result items, newest first; items with the same time keep the newest written first."""
    try:
        auto = results()
    except Exception:
        auto = []
    items = list(reversed(stored())) + auto
    return sorted(items, key=lambda i: -epoch(i.get("ts", "")))


def ago(t: float) -> str:
    d = int(time.time() - t)
    if d < 60:
        return "just now"
    return f"{d // 60} min ago" if d < 3600 else f"{d // 3600} h {d % 3600 // 60} min ago"


def card(i: dict) -> str:
    kind = i.get("kind", "")
    t = epoch(i.get("ts", ""))
    when = f'{time.strftime("%H:%M", time.gmtime(t))} UTC · {ago(t)}' if t else "time unknown"
    who = (f'<div class="who"><span>{escape(data.label(i["strategy"]))}</span> {escape(i["strategy"])}</div>' if i.get("strategy") else "")
    text = "<br>".join(escape(l) for l in str(i.get("text", "")).splitlines())
    return (f'<div class="up{" champ" if kind == "champion" else ""}"><div class="uh">{ui.tag(KINDS.get(kind, kind.capitalize() or "Update"))}<span>{when}</span></div>'
            f'<b>{escape(str(i["title"]))}</b>' + (f"<p>{text}</p>" if text else "") + who + "</div>")


@st.fragment(run_every=15)
@board.guarded
def updates() -> None:
    board.title("Updates", f"updated {data.stamp()} · newest first · times are UTC · refreshes every 15 s")
    items = feed()
    if not FILE.exists():
        st.info("No updates written yet: updates.jsonl does not exist. Add one with `uv run scripts/note.py <kind> \"<title>\" \"<text>\"`.")
    pick = st.segmented_control("Kind", ["All"] + list(KINDS.values()), default="All", key="up_kind", label_visibility="collapsed") or "All"
    if pick != "All":
        items = [i for i in items if KINDS.get(i.get("kind", "")) == pick]
    if not items:
        ui.html('<div class="empty">Nothing of this kind yet.</div>')
        return
    ui.html("".join(card(i) for i in items[:SHOWN]))
    st.caption(f"{min(len(items), SHOWN)} of {len(items)} items. Results of each finished 30-minute window come from the per-model leaderboard; "
               "everything else is written to updates.jsonl by us, the agents and the operator.")


@st.fragment(run_every=15)
@board.guarded
def latest(n: int = 3) -> None:
    lines = [f'<p class="ul">{time.strftime("%H:%M", time.gmtime(epoch(i.get("ts", ""))))} UTC · <b>{escape(str(i["title"]))}</b> '
             f'<small>· {escape(KINDS.get(i.get("kind", ""), i.get("kind", "")).lower())}</small></p>' for i in feed()[:n]]
    if lines:
        ui.html("".join(lines))
