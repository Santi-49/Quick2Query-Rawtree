"""quick2query dashboard: the development of the recommender at a glance. Read-only.

    uv run --group dashboard streamlit run dashboard/app.py

Now                       what is running: arms per kind of request, their traffic and live scores (board.py)
Leaderboard               our models per kind of request and every team, from the per-model leaderboard (leaderboard.py)
Strategies                cards: tested, testing now, up next (board.py)
Hypotheses and knowledge  what we know about the simulator (knowledge.toml) and the hypotheses behind it
Plan and backlog          the next windows, the ideas not built yet, the journal of decisions
Raw data                  any RawTree table, as stored
Every tab but the last refreshes on its own (st.fragment) and shows when; reads are cached, see data.py.
The "Details" button of a card opens a dialog.
"""
import json
import math
import re
from html import escape

import streamlit as st

import board
import data
import leaderboard
import ui
from q2q import evaluate, rt

ROOT = rt.ROOT
TABLES = ["shop.requests", "shop.events", "shop.catalog", "shop.catalog_updates", "shop.history_sessions",
          "shop.history_events", "{TEAM}.submissions", "{TEAM}.feedback", "{TEAM}.scratch"]

st.set_page_config(page_title="quick2query", layout="wide")
ui.html(ui.CSS)


# ---------- header ----------
@st.fragment(run_every=30)
def header() -> None:
    cfg = data.arms()
    champion = cfg["champion"]
    cells = ['<div class="brand">quick2query</div>',
             f'<div><span>Champion</span><b style="text-transform:capitalize">{escape(data.label(champion))}</b> <small>{escape(champion)}</small></div>']
    try:
        standing = data.report("standing")
        teams = standing[~standing.team_id.isin(["baseline", "reference"])].sort_values("conv", ascending=False).reset_index(drop=True)
        row = lambda t: standing[standing.team_id == t].iloc[0]
        us, base, ref = row(rt.TEAM), row("baseline"), row("reference")
        score = lambda r: 100 * (r.conv - base.conv) / evaluate.ORACLE_GAP
        cells.append(f'<div><span>Our score, last hour</span><b>{score(us):.0f}</b> <small>reference {score(ref):.0f} · conversion {us.conv:.2f}%</small></div>')
        cells.append(f'<div><span>Rank</span><b>{int(teams.index[teams.team_id == rt.TEAM][0]) + 1} of {len(teams)}</b> <small>best team {score(teams.iloc[0]):.0f}</small></div>')
    except Exception:
        cells.append('<div><span>Our score, last hour</span><b>not available</b> <small>no leaderboard reading in RawTree</small></div>')
    try:
        now = data.report("now").iloc[0]
        answered, p95 = 100 * now.answered / max(now.requests, 1), now.p95_ms / 1000
        health = "Healthy" if answered >= 98 and p95 < 2.5 else "Degraded" if answered >= 50 else "Down"
        cells.append(f'<div><span>Router, last 10 min</span><b>{health}</b> <small>{answered:.1f}% answered · p95 {p95:.2f} s of 3 s</small></div>')
    except Exception:
        cells.append('<div><span>Router, last 10 min</span><b>not available</b> <small>feedback could not be read</small></div>')
    ui.html(f'<div class="hd">{"".join(cells)}</div><div class="stamp">updated {data.stamp()} · refreshes every 30 s · score 0 is the baseline, 100 the hidden model\'s own picks</div>')


# ---------- hypotheses and knowledge ----------
def knowledge() -> None:
    k = data.knowledge()
    factors = k["factors"]
    if not factors:
        st.info("knowledge.toml has no factors yet.")
        return
    board.title("What moves the chance of a purchase", f"updated {data.stamp()} · from knowledge.toml · refreshes every 60 s")
    top = max(abs(math.log(max(float(f.get("size", 1)), 1e-6))) for f in factors) or 1

    def row(i: int, f: dict) -> str:
        size = float(f.get("size", 1))
        width = max(100 * abs(math.log(max(size, 1e-6))) / top, 2)
        down = size < 1
        users = ", ".join(data.label(n) for n in f.get("used_by", [])) or "no strategy yet"
        return (f'<div class="kn"><div class="rk">{i}</div>'
                f'<div class="fx"><b>{escape(f.get("factor", ""))}</b><p>{escape(f.get("effect", ""))}</p><small>used by {escape(users)}</small></div>'
                f'<div class="mz"><span class="kn-size">×{size:g}<small>{"lowers" if down else "raises"} {escape(f.get("measure", ""))}</small></span>'
                f'<div class="kb" role="img" aria-label="times {size:g}"><div class="{"down" if down else ""}" style="width:{width:.0f}%"></div></div></div>'
                f'<div class="ev">{ui.tag(f.get("evidence", ""))}</div></div>')

    firm = [f for f in factors if f.get("evidence") in data.EVIDENCE[:2]]
    rest = [f for f in factors if f not in firm]
    shown = min(len(firm), 8)
    with st.container(border=True, key="card_knowledge"):
        ui.html("".join(row(i + 1, f) for i, f in enumerate(firm[:shown])))
    left, right = st.columns(2)
    if firm[shown:]:
        with left.expander(f"{len(firm) - shown} smaller confirmed factors"):
            ui.html("".join(row(i + shown + 1, f) for i, f in enumerate(firm[shown:])))
    if rest:
        with right.expander(f"{len(rest)} factors not confirmed on live purchases yet"):
            ui.html("".join(row(i + len(firm) + 1, f) for i, f in enumerate(rest)))
    st.caption("Confirmed on our own live feedback, largest effect first. Bars are on a log scale: ×0.36 is as long as ×2.8. Solid bars raise the chance, striped bars lower it.")
    a, c = st.columns(2, gap="medium")
    for col, key, name in ((a, "lessons", "Rules we work by"), (c, "no_effect", "Tested, makes no difference")):
        if k[key]:
            with col.container(border=True, key=f"card_{key}"):
                ui.html(f'<div class="ch"><span class="nm plain">{name}</span></div><ul class="lessons">' + "".join(f"<li>{escape(x)}</li>" for x in k[key]) + "</ul>")
    sources = [f for f in factors if f.get("source")]
    a, c, _ = st.columns([3, 1, 3], vertical_alignment="bottom")
    pick = a.selectbox("Open the evidence behind a factor", range(len(sources)), format_func=lambda i: f"{sources[i]['factor']} · {sources[i]['source']}", key="knowledge_pick")
    if c.button("Open evidence", key="knowledge_open"):
        board.open_detail("hypothesis", sources[pick]["source"])


@st.fragment(run_every=60)
@board.guarded
def learned() -> None:
    knowledge()
    board.hypotheses()


# ---------- plan and backlog ----------
@st.fragment(run_every=60)
@board.guarded
def plan() -> None:
    reg = data.registry()
    board.title("Plan for the next windows", f"updated {data.stamp()} · from strategies.toml · times are UTC · refreshes every 60 s")
    if reg["plan"]:
        with st.container(border=True, key="card_plan"):
            ui.html("".join(f'<div class="pl"><div class="wh"><b>{escape(str(p.get("when", "")))}</b>{ui.tag(data.plan_state(p.get("when", "")))}</div>'
                            f'<div><p>{escape(str(p.get("what", "")))}</p><p class="rule"><b>Decision rule.</b> {escape(str(p.get("decide", "")))}</p></div></div>' for p in reg["plan"]))
    else:
        st.caption("strategies.toml has no [[plan]] entries.")
    log = ROOT / "logs/operator.out.log"
    if log.exists():
        last = [l.strip() for l in log.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()][-3:]
        ui.html('<p class="line">The operator script edits arms.toml on its own. Its last lines: ' + " · ".join(escape(l[:160]) for l in reversed(last)) + "</p>")
    st.markdown(f"### Backlog · {len(reg['backlog'])} ideas not built yet")
    if reg["backlog"]:
        with st.container(border=True, key="card_backlog"):
            ui.html("".join(f'<div class="pl wide"><div class="wh"><b>{escape(str(b.get("idea", "")))}</b></div>'
                            f'<div><p>{escape(str(b.get("why", "")))}</p><p class="rule">size {escape(str(b.get("size", "unknown")))}'
                            + (f' · rests on hypothesis {escape(str(b["hypothesis"]))}' if b.get("hypothesis") else "") + "</p></div></div>" for b in reg["backlog"]))
    st.markdown("### Done so far: the latest decisions")
    lines = [l for l in (ROOT / "docs/JOURNAL.md").read_text(encoding="utf-8").splitlines() if l.startswith("- ")]
    st.markdown("\n".join(reversed(lines[-4:])))
    with st.expander(f"The whole journal · {len(lines)} dated decisions, newest first"):
        st.markdown("\n".join(reversed(lines)))


# ---------- raw data ----------
def raw() -> None:
    q = data.q
    a, c, d, e = st.columns([2, 1, 1, 2])
    table = a.selectbox("Table", TABLES).replace("{TEAM}", rt.TEAM)
    n = c.slider("Rows", 10, 200, 25)
    columns = list(q(f"SELECT * FROM {table} LIMIT 1").columns)
    where = []
    if table.endswith(".scratch"):
        kind = d.selectbox("kind", ["(all)"] + sorted(q(f"SELECT DISTINCT kind::String AS kind FROM {table}").kind))
        if kind != "(all)" and re.fullmatch(r"[A-Za-z0-9_]+", kind):
            where.append(f"kind::String = '{kind}'")
    ids = [x for x in ("request_id", "user_id", "product_id") if x in columns]
    if ids:
        col = d.selectbox("Filter on", ["(none)"] + ids, key="idcol")
        value = e.text_input("equals", key="idval")
        if col != "(none)" and value:
            if re.fullmatch(r"[A-Za-z0-9_]+", value):
                where.append(f"{col}::String = '{value}'")
            else:
                e.warning("Only letters, digits and underscores.")
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    order = " ORDER BY ts DESC" if "ts" in columns else ""
    sql = f"SELECT * FROM {table}{clause}{order} LIMIT {n}"
    total = q(f"SELECT count() AS n FROM {table}{clause}").n.iloc[0]
    st.caption(f"{int(total):,} rows match · {len(columns)} columns · read at {data.stamp()}, kept for 30 s · `{sql}`")
    rows = q(sql)
    for name in rows.columns:
        if rows[name].map(lambda v: isinstance(v, (list, dict))).any():
            rows[name] = rows[name].map(lambda v: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v)
    st.dataframe(rows, hide_index=True, width="stretch", height=520)


# ---------- page ----------
def safe(tab, body) -> None:
    """Run one tab; a failing read shows a warning and the other tabs still render."""
    with tab:
        try:
            body()
        except Exception as e:
            st.warning(f"This view could not be built: {e}")


header()
tabs = st.tabs(["Now", "Leaderboard", "Strategies", "Hypotheses and knowledge", "Plan and backlog", "Raw data"])
for tab, body in zip(tabs, (board.now, leaderboard.leaderboard, board.strategies, learned, plan, raw)):
    safe(tab, body)
board.show_pending()
