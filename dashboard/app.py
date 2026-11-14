"""quick2query dashboard: the development of the recommender at a glance. Read-only.

    uv run --group dashboard streamlit run dashboard/app.py

Board      strategies and hypotheses as cards: tested, testing now, up next (board.py)
Knowledge  what we know about the simulator, ranked by effect size (knowledge.toml)
Live       who is answering right now
Raw tables any table, as stored
More       plan, journal, how it works, one live request
The header, the Board and the Live tab refresh on their own; a card's "Details" opens a dialog.
"""
import json
import math
import re
import time
from html import escape

import pandas as pd
import streamlit as st

import board
import data
import ui
from q2q import evaluate, rt, serve
from q2q.strategy import Request, guard, label, load

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
    cells = [f'<div class="brand">quick2query</div>',
             f'<div><span>Champion</span><b style="text-transform:capitalize">{escape(label(champion))}</b> <small>{escape(champion)}</small></div>']
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
    ui.html(f'<div class="hd">{"".join(cells)}</div><div class="stamp">updated {data.stamp()} · score 0 is the baseline, 100 the hidden model\'s own picks</div>')


# ---------- knowledge ----------
def knowledge() -> None:
    k = data.knowledge()
    factors = k["factors"]
    if not factors:
        st.info("knowledge.toml has no factors yet.")
        return
    counts = pd.Series([f.get("evidence", "") for f in factors]).value_counts()
    st.markdown("### What moves the chance of a purchase, strongest first")
    ui.html(" ".join(f'{ui.tag(e)} <span class="stamp" style="margin-right:14px">{n}</span>' for e, n in counts.items()))
    top = max(abs(math.log(max(float(f.get("size", 1)), 1e-6))) for f in factors) or 1

    def row(i: int, f: dict) -> str:
        size = float(f.get("size", 1))
        width = max(100 * abs(math.log(max(size, 1e-6))) / top, 2)
        down = size < 1
        users = ", ".join(label(n) for n in f.get("used_by", [])) or "no strategy yet"
        return (f'<div class="kn"><div class="rk">{i}</div>'
                f'<div class="fx"><b>{escape(f.get("factor", ""))}</b><p>{escape(f.get("effect", ""))}</p><small>used by {escape(users)}</small></div>'
                f'<div class="mz"><span class="kn-size">×{size:g}<small>{"lowers" if down else "raises"} {escape(f.get("measure", ""))}</small></span>'
                f'<div class="kb" role="img" aria-label="times {size:g}"><div class="{"down" if down else ""}" style="width:{width:.0f}%"></div></div></div>'
                f'<div class="ev">{ui.tag(f.get("evidence", ""))}</div></div>')

    shown = 10
    with st.container(border=True, key="card_knowledge"):
        ui.html("".join(row(i + 1, f) for i, f in enumerate(factors[:shown])))
    if len(factors) > shown:
        with st.expander(f"{len(factors) - shown} smaller factors"):
            ui.html("".join(row(i + shown + 1, f) for i, f in enumerate(factors[shown:])))
    st.caption("Bars are on a log scale: ×0.36 is as long as ×2.8. Solid bars raise the chance, striped bars lower it. "
               + ("Tested and found to make no difference: " + "; ".join(k["no_effect"]) + "." if k["no_effect"] else ""))
    sources = [f for f in factors if f.get("source")]
    a, c, _ = st.columns([3, 1, 3], vertical_alignment="bottom")
    pick = a.selectbox("Open the evidence behind a factor", range(len(sources)), format_func=lambda i: f"{sources[i]['factor']} · {sources[i]['source']}", key="knowledge_pick")
    if c.button("Open evidence", key="knowledge_open"):
        st.session_state["detail"] = ("hypothesis", sources[pick]["source"])


# ---------- live ----------
@st.fragment(run_every=15)
def live() -> None:
    cfg = data.arms()
    try:
        df = data.live()
    except Exception as e:
        st.warning(f"Live traffic could not be read: {e}")
        return
    if df.empty:
        st.info("No requests in the last 5 minutes.")
        return
    plan, unanswered = data.serving(cfg), int((df.strategy == "").sum())
    head = st.columns([3, 2], vertical_alignment="bottom")
    head[0].markdown("### Who is answering, last 5 minutes")
    head[1].markdown(f'<div class="stamp" style="text-align:right">updated {data.stamp()} · {len(df):,} requests · {unanswered} not answered yet · refreshes every 15 s</div>', unsafe_allow_html=True)
    for col, route in zip(st.columns(3, gap="medium"), data.ROUTES):
        part = df[df.route == route]
        mix = part[part.strategy != ""].strategy.value_counts()
        rows = "".join(f'<span style="text-transform:capitalize">{escape(label(n))} <small style="text-transform:none">{escape(n)}'
                       f'{"" if n in plan[route] or n == "explore" else " · not in arms.toml"}</small></span><b class="num">{100 * c / max(len(part), 1):.0f}%</b>'
                       f'<div class="bar" style="grid-column:1/-1"><div style="width:{100 * c / max(len(part), 1):.0f}%"></div></div>' for n, c in mix.items())
        with col.container(border=True, key=f"card_live_{route}"):
            ui.html(f'<div class="lv"><div class="ch"><b style="text-transform:capitalize">{data.ROUTES[route]}</b><span class="stamp">{100 * len(part) / len(df):.0f}% of requests</span></div>'
                    f'<div class="sub">{data.ROUTE_HELP[route]} · arms.toml: {escape(", ".join(plan[route]))} split evenly, explore {100 * cfg["explore_share"]:.0f}%</div>'
                    f'<div class="who">{rows or "<span>no answers yet</span>"}</div></div>')
    with st.expander("Each shopper, newest first"):
        df = df.assign(result=["bought" if p else "clicked" if c else "fallback" if s == "fallback" else "" for p, c, s in zip(df.purchased, df.clicked, df.served_by)],
                       shopper=df.new_shopper.map({True: "new", False: "returning"}), kind=df.route.map(data.ROUTES))
        df["public name"] = df.model_version
        st.dataframe(df[["time", "kind", "page", "shopper", "device", "region", "views", "strategy", "public name", "latency_ms", "result"]].head(200), hide_index=True, height=420,
                     column_config={"latency_ms": st.column_config.NumberColumn("latency ms", format="%.0f")})


# ---------- raw tables ----------
def raw() -> None:
    q = data.q
    a, c, d, e = st.columns([2, 1, 1, 2])
    table = a.selectbox("Table", TABLES).replace("{TEAM}", rt.TEAM)
    n = c.slider("Rows", 10, 200, 25)
    sample = rt.query(f"SELECT * FROM {table} LIMIT 1")
    columns = list(sample[0]) if sample else []
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
    st.caption(f"{int(total):,} rows match · {len(columns)} columns · `{sql}`")
    rows = q(sql)
    for name in rows.columns:
        if rows[name].map(lambda v: isinstance(v, (list, dict))).any():
            rows[name] = rows[name].map(lambda v: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v)
    st.dataframe(rows, hide_index=True, width="stretch", height=520)


# ---------- more ----------
@st.cache_resource(show_spinner="Loading the live state (about 20 s)...")
def live_state():
    from q2q.state import State
    s = State()
    s.load()
    return s


def one_request() -> None:
    cfg = data.arms()
    reqs = rt.query(serve.POLL.replace("LIMIT 60", "LIMIT 30"))
    state = live_state()
    labels = [f"{time.strftime('%H:%M:%S', time.gmtime(r['ts_ms'] / 1000))} · {r['page']} · {r['device']} · {r['region']} · "
              f"{'new' if r['is_new_user'] else 'returning'} · {len(r['views'])} views" for r in reqs]
    r = reqs[st.selectbox("Request, newest first", range(len(reqs)), format_func=labels.__getitem__)]
    P, views, shopper = state.products, list(r["views"]), state.shopper(r["user_id"])
    top = sorted(shopper.cat_share.items(), key=lambda kv: -kv[1])[:3] if shopper else []
    lifts = sorted(((k, v) for k, v in state.segment.get((r["device"], r["region"]), {}).items() if v > 1.5), key=lambda kv: -kv[1])
    a, c = st.columns(2)
    a.markdown(f"**The shopper.** Known: {'yes' if shopper else 'no'} · bought {len(shopper.bought) if shopper else 0} · viewed before, not bought {len(shopper.viewed) if shopper else 0}  \n"
               f"Favourite categories: {', '.join(f'{k} {100 * v:.0f}%' for k, v in top) or 'none'}  \n"
               f"Segment {r['device']} × {r['region']}: {', '.join(f'{k} ×{v:.1f}' for k, v in lifts) or 'no category above ×1.5'}")
    if views:
        c.dataframe(pd.DataFrame([{"recent view": P[p].subcategory, "brand": P[p].brand, "price €": P[p].price, "in stock": state.available(p)} for p in views if p in P]),
                    hide_index=True, height=38 + 35 * min(len(views), 4))
    else:
        c.caption("No recent views. The answer rests on the shopper's history and their segment.")
    subs, cats = {P[p].subcategory for p in views if p in P}, {P[p].category for p in views if p in P}
    mark = lambda p: "viewed" if p in views else "same subcategory" if P[p].subcategory in subs else "same category" if P[p].category in cats else ""
    names = [s["name"] for s in data.strategies(cfg, data.registry()) if s["has_file"]]
    chosen = st.multiselect("Strategies to compare", names, default=[n for n in names if n in data.running(cfg)][:3], max_selections=4, format_func=lambda n: f"{label(n)} ({n})")
    for col, name in zip(st.columns(max(len(chosen), 1)), chosen):
        try:
            strat = load(name)
            req = Request(r["request_id"], r["ts_ms"] / 1000, r["user_id"], bool(r["is_new_user"]), r["page"], r["device"], r["region"], views)
            items = guard(strat.recommend(req, state), state)
        except Exception as e:
            col.warning(f"{name} could not answer here: {e}")
            continue
        col.markdown(f"**{label(name)}** ({name})" + (" · champion" if name == cfg["champion"] else ""))
        col.dataframe(pd.DataFrame([{"#": k + 1, "subcategory": P[p].subcategory, "brand": P[p].brand, "link": mark(p)} for k, p in enumerate(items)]), hide_index=True, height=388)
    st.caption("The strategies run again on this page's own copy of the state, so answers can differ slightly from what the router sent.")


def more() -> None:
    reg = data.registry()
    with st.expander(f"Plan for the next windows · {len(reg['plan'])} steps", expanded=True):
        if reg["plan"]:
            st.dataframe(pd.DataFrame(reg["plan"]), hide_index=True, width="stretch",
                         column_config={"what": st.column_config.TextColumn("what runs", width="large"), "decide": st.column_config.TextColumn("decision rule", width="large")})
        else:
            st.caption("strategies.toml has no [[plan]] entries.")
    with st.expander("Journal: dated decisions, newest first"):
        lines = (ROOT / "docs/JOURNAL.md").read_text(encoding="utf-8").splitlines()
        st.markdown("\n".join(reversed([l for l in lines if l.startswith("- ")])))
    with st.expander("How it works"):
        st.graphviz_chart("""digraph { rankdir=LR; bgcolor="transparent"; node [shape=box, style="rounded", fontname=Helvetica, color="#8FA3C7", fontcolor="#E6EBF4"];
          edge [fontname=Helvetica, fontsize=10, color="#8FA3C7", fontcolor="#C9D2E3"];
          shoppers -> "shop.requests" -> arm;
          subgraph cluster_router { label="router"; color="#56B4E9"; fontcolor="#56B4E9"; style=rounded;
            state; arm [label="arm choice"]; strategy; guard; state -> strategy; arm -> strategy -> guard; }
          "shop.events" -> state; "shop.catalog_updates" -> state;
          guard -> "submissions" -> simulator; simulator -> "feedback"; simulator -> leaderboard;
          leaderboard -> "per-model scores" -> "arms.toml" -> arm [label="hot reload"]; }""", width="stretch")
        st.markdown((ROOT / "docs/EXPLAINER.md").read_text(encoding="utf-8"))
    with st.expander("One live request: what each strategy would answer"):
        if st.toggle("Load the live state and the newest requests (about 20 s)", key="one_request_on"):
            one_request()


# ---------- page ----------
def safe(tab, body) -> None:
    """Run one tab; a failing read shows a warning and the other tabs still render."""
    with tab:
        try:
            body()
        except Exception as e:
            st.warning(f"This view could not be built: {e}")


header()
tabs = st.tabs(["Board", "Knowledge", "Live", "Raw tables", "More"])
for tab, body in zip(tabs, (board.render, knowledge, live, raw, more)):
    safe(tab, body)
board.show_pending()
