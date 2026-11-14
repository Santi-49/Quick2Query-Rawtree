"""quick2query dashboard: what is working, live. Read-only.

    uv run --group dashboard streamlit run dashboard/app.py
"""
import json
import re
import time

import altair as alt
import pandas as pd
import streamlit as st

import board as strategies_tab
from q2q import evaluate, rt, serve
from q2q.strategy import Request, decode, guard, load, route_of

ROOT = rt.ROOT
OKABE = ["#56B4E9", "#E69F00", "#009E73", "#CC79A7", "#F0E442", "#D55E00", "#0072B2"]  # colour-blind safe
GREY = "#5B6577"
PCT = st.column_config.NumberColumn(format="%.2f%%")
TABLES = ["shop.requests", "shop.events", "shop.catalog", "shop.catalog_updates", "shop.history_sessions",
          "shop.history_events", "{TEAM}.submissions", "{TEAM}.feedback", "{TEAM}.scratch"]

st.set_page_config(page_title="quick2query", layout="wide")
st.markdown("""<style>
.block-container {padding: 2.2rem 2rem 2rem; max-width: 1500px}
[data-testid="stMetric"] {background: #161E2E; border: 1px solid #263147; border-radius: 8px; padding: .6rem .8rem}
[data-testid="stMetricLabel"] p {font-size: .78rem; color: #9AA7BD}
[data-testid="stMetricValue"] {font-size: 1.45rem; font-variant-numeric: tabular-nums}
h1 {font-size: 1.3rem !important; padding: 0 0 .4rem !important}
h3 {font-size: 1rem !important; padding-top: .4rem !important}
.tag {display: inline-block; padding: 1px 8px; border-radius: 10px; border: 1px solid #3A4865; font-size: .78rem}
</style>""", unsafe_allow_html=True)


@st.cache_data(ttl=30, show_spinner=False)
def q(sql: str) -> pd.DataFrame:
    return pd.DataFrame(rt.query(sql))


def report(name: str) -> pd.DataFrame:
    return q((ROOT / "sql" / "reports" / f"{name}.sql").read_text(encoding="utf-8"))


@st.cache_data(ttl=30, show_spinner=False)
def blocks() -> pd.DataFrame:
    return pd.DataFrame(evaluate.blocks())


@st.cache_resource(show_spinner="Loading the live state (about 5 s)...")
def live_state():
    from q2q.state import State
    s = State()
    s.load()
    return s


def arm_colours(arms) -> alt.Scale:
    """The same colour for the same arm on every chart."""
    known = sorted(f.stem for f in (ROOT / "src/q2q/strategies").glob("*.py") if f.stem != "__init__")
    domain = [a for a in known if a in set(arms)] + sorted(set(arms) - set(known))
    return alt.Scale(domain=domain, range=[OKABE[known.index(a) % len(OKABE)] if a in known else GREY for a in domain])


def safe(tab, body):
    """Run one tab; a failing query shows a warning and the other tabs still render."""
    with tab:
        try:
            body()
        except Exception as e:
            st.warning(f"This view could not be built: {e}")


with st.sidebar:
    if st.button("Refresh now"):
        st.cache_data.clear()
    auto = st.toggle("Refresh every 30 s", value=False)
    st.caption("Reads are cached for 30 s. This page only reads RawTree.")

cfg, _ = serve.Arms().get()
champion = cfg["champion"]

# ---------- header ----------
st.title("quick2query · live")
try:
    board = report("standing")
    teams = board[~board.team_id.isin(["baseline", "reference"])].sort_values("conv", ascending=False).reset_index(drop=True)
    row = lambda t: board[board.team_id == t].iloc[0]
    us, base, ref = row(rt.TEAM), row("baseline"), row("reference")
    now = report("now").iloc[0]
    block_arm = serve.arm_for(Request("", time.time(), "header", False, "product", "", "", ["x"]), {**cfg, "explore_share": 0})
    m = st.columns(6)
    m[0].metric("Champion", champion)
    m[1].metric("Our conversion, last hour", f"{us.conv:.2f}%", f"{us.conv - base.conv:+.2f} pts vs baseline")
    m[2].metric("Score, last hour", f"{100 * (us.conv - base.conv) / evaluate.ORACLE_GAP:.0f} / 100",
                f"reference {100 * (ref.conv - base.conv) / evaluate.ORACLE_GAP:.0f}", delta_color="off")
    m[3].metric("Rank", f"{int(teams.index[teams.team_id == rt.TEAM][0]) + 1} of {len(teams)}", f"best {teams.conv.iloc[0]:.2f}%", delta_color="off")
    m[4].metric("Answered by us, last 10 min", f"{100 * now.answered / max(now.requests, 1):.1f}%")
    m[5].metric("Latency p95, last 10 min", f"{now.p95_ms / 1000:.2f} s", "deadline 3 s", delta_color="off")
    st.caption(f"Leaderboard refresh {us.ts[11:19]} UTC. Score: 0 is the baseline, 100 the hidden model's own picks.")
except Exception as e:
    st.warning(f"Header numbers unavailable: {e}")

tabs = st.tabs(["Live traffic", "Strategies", "Overview", "One live request", "Hypotheses", "Explore arm", "Backlog and journal", "Raw tables", "How it works"])


# ---------- 0. live traffic ----------
def live():
    df = report("live")
    if df.empty:
        st.info("No requests in the last 5 minutes.")
        return
    df["strategy"] = df.model_version.map(lambda m: decode(m) if m else "(no answer)")
    df["route"] = df.model_version.map(lambda m: {"": "ordinary", "no_views": "no recent views", "new_shopper": "new shopper"}[route_of(m)] if m else "")
    a, c = st.columns([1, 2])
    a.markdown("### Who is answering, last 5 minutes")
    df["public name"] = df.model_version.fillna("")
    mix = df.groupby(["route", "strategy", "public name"], as_index=False).agg(requests=("time", "size"), clicks=("clicked", "sum"), purchases=("purchased", "sum"))
    mix["share"] = 100 * mix.requests / mix.requests.sum()
    a.dataframe(mix.sort_values("requests", ascending=False), hide_index=True, column_config={"share": PCT})
    a.markdown("### What should be running (arms.toml)")
    lines = [f"- ordinary requests: **{', '.join(cfg['schedule']) or champion}**"]
    lines += [f"- {k.replace('_', ' ')}: **{', '.join(v) or 'as ordinary'}**" for k, v in cfg["routes"].items()]
    lines += [f"- explore: {100 * cfg['explore_share']:.0f}% of shoppers", "", "Several arms on one line split the shoppers evenly at the same time."]
    a.markdown(chr(10).join(lines))
    per = df.groupby([df.time.str[:5], "strategy"], as_index=False).size()
    c.altair_chart(alt.Chart(per).mark_bar().encode(x=alt.X("time:N", title="Minute (UTC)"), y=alt.Y("size:Q", title="Requests answered"),
                   color=alt.Color("strategy:N", scale=arm_colours(per.strategy), legend=alt.Legend(orient="top", title=None)), tooltip=["time", "strategy", "size"]).properties(height=190), width="stretch")
    c.markdown("### Each shopper, newest first")
    df["result"] = df.apply(lambda r: "bought" if r.purchased else "clicked" if r.clicked else "fallback" if r.served_by == "fallback" else "", axis=1)
    df["shopper"] = df.new_shopper.map({True: "new", False: "returning"})
    c.dataframe(df[["time", "page", "shopper", "device", "region", "views", "strategy", "public name", "route", "latency_ms", "result"]].head(200), hide_index=True, height=420,
                column_config={"latency_ms": st.column_config.NumberColumn("latency ms", format="%.0f")})
    c.caption("Turn on \"Refresh every 30 s\" in the sidebar to follow it. Feedback arrives about a second after each request.")


# ---------- 1. overview ----------
def overview():
    b = blocks()
    left, right = st.columns([2, 1])
    if b.empty or b["score"].isna().all():
        left.info("No block with a known lift yet.")
        return
    b = b.dropna(subset=["score"]).copy()
    b["time"] = b.block_end.str[11:16]
    b["outage"] = b.answered.fillna(0) < 0.5
    b["arm"] = b.arm.where(~b.outage, "outage").replace("", "outage")
    good = b[~b.outage]
    base = alt.Chart(b.tail(36)).encode(x=alt.X("time:N", title="10-minute block ending (UTC)", sort=None))
    bars = base.mark_bar().encode(y=alt.Y("score:Q", title="Score of the block (0 baseline, 100 oracle)"),
                                  color=alt.Color("arm:N", scale=arm_colours(b.arm), legend=alt.Legend(orient="top", title=None)),
                                  tooltip=["time", "arm", alt.Tooltip("score:Q", format="+.1f"), alt.Tooltip("lift:Q", format="+.2f"), "requests"])
    names = base.mark_text(dy=-6, fontSize=10, color="#C9D2E3").encode(y="score:Q", text="arm:N")
    ref = base.mark_line(color="#E6EBF4", strokeDash=[5, 4]).encode(y="ref_window_score:Q")
    left.altair_chart((bars + names + ref).properties(height=330), width="stretch")
    left.caption("Bars: our lift over the baseline in each block, read from the leaderboard. Dashed line: the reference recommender over the last hour. "
                 "Outage blocks (under half answered) are grey and left out of every average.")

    summary = pd.DataFrame(evaluate.by_arm(good.to_dict("records")))
    summary = summary.merge(good.groupby("arm").purchase_rate.mean().mul(100).rename("purchase").reset_index(), on="arm")
    champ = summary[summary.arm == champion]
    champ_score = champ.score.iloc[0] if len(champ) else None

    def verdict(r):
        if r.arm == champion:
            return "champion"
        if r.blocks < 2 or champ_score is None:
            return "too early"
        gap = r.score - champ_score
        return f"beats champion by {gap:+.1f}" if gap > 0 else f"behind champion by {gap:+.1f}"
    summary["verdict"] = summary.apply(verdict, axis=1)
    summary["click_rate"] *= 100
    right.markdown("### Verdict per strategy")
    right.dataframe(summary.sort_values("score", ascending=False)[["arm", "verdict", "blocks", "score", "se", "click_rate", "purchase"]], hide_index=True,
                    column_config={"score": st.column_config.NumberColumn("mean score", format="%+.1f"), "se": st.column_config.NumberColumn("± se", format="%.1f"),
                                   "click_rate": st.column_config.NumberColumn("click", format="%.2f%%"), "purchase": st.column_config.NumberColumn("buy", format="%.2f%%")})
    right.caption("A challenger needs to win three alternated block pairs. One block is exact to about ±1 score point.")

    seg = report("segments")
    if seg.empty:
        return
    seg["arm"] = seg.model_version.map(decode)
    seg["segment"] = seg.page + " · " + seg.new_user.map({True: "new shopper", False: "returning"})
    g = seg.groupby(["segment", "arm"], as_index=False)[["requests", "clicks", "purchases"]].sum()
    g["cell"] = g.apply(lambda r: f"{100 * r.purchases / r.requests:.2f}% buy · {100 * r.clicks / r.requests:.2f}% click · n {int(r.requests):,}", axis=1)
    table = g.pivot(index="segment", columns="arm", values="cell").fillna("")
    big = g[g.requests >= 300].copy()
    big["buy"] = 100 * big.purchases / big.requests
    best = big.loc[big.groupby("segment").buy.idxmax()].set_index("segment")
    table["best with n ≥ 300"] = [f"{best.arm[s]} ({best.buy[s]:.2f}%)" if s in best.index else "too few" for s in table.index]
    st.markdown("### Where each strategy works: purchase and click rate per request, last 3 hours")
    st.dataframe(table, width="stretch")
    mine = big[big.arm == champion]
    if len(mine):
        w = mine.loc[mine.buy.idxmin()]
        st.caption(f"Weakest segment of the champion `{champion}`: **{w.segment}**, {w.buy:.2f}% purchases over {int(w.requests):,} requests. "
                   "Purchases are rare, so read differences under 300 requests as noise.")
    rel = report("reliability")
    if not rel.empty:
        rel["answered %"] = 100 * rel.answered / rel.requests
        rel["time"] = rel.t.str[11:16]
        a, c = st.columns(2)
        a.altair_chart(alt.Chart(rel).mark_area(opacity=.5, color=OKABE[2]).encode(x=alt.X("time:N", title="10 minutes starting (UTC)", sort=None),
                       y=alt.Y("answered %:Q", title="Answered by us, %")).properties(height=150), width="stretch")
        lat = rel.melt(id_vars="time", value_vars=["p50_ms", "p95_ms"], var_name="quantile", value_name="ms")
        c.altair_chart(alt.Chart(lat).mark_line().encode(x=alt.X("time:N", title="10 minutes starting (UTC)", sort=None), y=alt.Y("ms:Q", title="Latency of our answers, ms"),
                       color=alt.Color("quantile:N", scale=alt.Scale(range=[OKABE[0], OKABE[1]]), legend=alt.Legend(orient="top", title=None)),
                       strokeDash="quantile:N").properties(height=150), width="stretch")


# ---------- 2. one live request ----------
def one_request():
    reqs = rt.query(serve.POLL.replace("LIMIT 60", "LIMIT 30"))
    state = live_state()
    labels = [f"{time.strftime('%H:%M:%S', time.gmtime(r['ts_ms'] / 1000))} · {r['page']} · {r['device']} · {r['region']} · "
              f"{'new' if r['is_new_user'] else 'returning'} · {len(r['views'])} views" for r in reqs]
    r = reqs[st.selectbox("Request, newest first", range(len(reqs)), format_func=labels.__getitem__)]
    P = state.products
    views = list(r["views"])
    shopper = state.shopper(r["user_id"])
    a, c = st.columns(2)
    top = sorted(shopper.cat_share.items(), key=lambda kv: -kv[1])[:3] if shopper else []
    lifts = sorted(((k, v) for k, v in state.segment.get((r["device"], r["region"]), {}).items() if v > 1.5), key=lambda kv: -kv[1])
    a.markdown("### The shopper")
    a.markdown(f"- Known: **{'yes' if shopper else 'no'}** · bought {len(shopper.bought) if shopper else 0} · viewed before, not bought {len(shopper.viewed) if shopper else 0}\n"
               f"- Favourite categories: {', '.join(f'{k} {100 * v:.0f}%' for k, v in top) or 'none'}\n"
               f"- Segment {r['device']} × {r['region']}: {', '.join(f'{k} ×{v:.1f}' for k, v in lifts) or 'no category above ×1.5'}")
    c.markdown("### Recent views, oldest first")
    if views:
        c.dataframe(pd.DataFrame([{"subcategory": P[p].subcategory, "brand": P[p].brand, "price €": P[p].price, "in stock": state.available(p)} for p in views if p in P]),
                    hide_index=True, height=38 + 35 * min(len(views), 4))
    else:
        c.caption("None. The answer rests on the shopper's history and their segment.")
    subs, cats = {P[p].subcategory for p in views if p in P}, {P[p].category for p in views if p in P}
    mark = lambda p: "viewed" if p in views else "same subcategory" if P[p].subcategory in subs else "same category" if P[p].category in cats else ""
    names = sorted((f.stem for f in (ROOT / "src/q2q/strategies").glob("*.py") if f.stem != "__init__"), key=lambda n: (n != champion, n))
    chosen = st.multiselect("Strategies to compare", names, default=[n for n in names if n in (champion, "baseline", "cold1", "explore")][:4], max_selections=4)
    for col, name in zip(st.columns(max(len(chosen), 1)), chosen):
        strat = load(name)
        req = Request(r["request_id"], r["ts_ms"] / 1000, r["user_id"], bool(r["is_new_user"]), r["page"], r["device"], r["region"], views)
        items = guard(strat.recommend(req, state), state)
        col.markdown(f"**{name}**" + (" · champion" if name == champion else ""))
        col.dataframe(pd.DataFrame([{"#": k + 1, "subcategory": P[p].subcategory, "brand": P[p].brand, "link": mark(p)} for k, p in enumerate(items)]), hide_index=True, height=388)
        if hasattr(strat, "explain"):
            col.caption("Score = product of these multipliers")
            col.dataframe(pd.DataFrame([{"product": P[p].subcategory, "score": round(s, 1), **{k: round(v, 2) for k, v in parts.items()}} for s, p, parts in strat.explain(req, state)]), hide_index=True)
        if req.log:
            col.caption(f"Drawn group: **{req.log.get('stratum')}**, propensity {req.log.get('propensity', 0):.3f}, pool of {req.log.get('pool', 0)}.")
    st.caption("The strategies run again on this page's own copy of the state, so answers can differ slightly from what the router sent.")


# ---------- 3. hypotheses ----------
def hypotheses():
    text = (ROOT / "docs/SIMULATOR.md").read_text(encoding="utf-8")
    rows = []
    for title in ("Verdicts on the first hypotheses", "New hypotheses"):
        for line in text.split(f"## {title}")[1].split("\n## ")[0].splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if line.startswith("|") and cells[0] not in ("Slug", "") and not set(cells[0]) <= {"-", " "}:
                rows.append({"slug": cells[0], "status": re.sub(r"\*", "", cells[1]).split(",")[0] if len(cells) == 4 else "open",
                             "claim or consequence": cells[-1] if len(cells) == 4 else cells[1]})
    for f in sorted((ROOT / "docs/hypotheses").glob("H-*.md")):
        status = re.search(r"\*\*status\*\*:\s*(.+)|^status:\s*(.+)", f.read_text(encoding="utf-8"), re.M)
        rows.append({"slug": f.stem[2:], "status": "tested", "claim or consequence": (status.group(1) or status.group(2))[:160] if status else ""})
    df = pd.DataFrame(rows)
    df["write-up"] = df.slug.map(lambda s: (ROOT / f"docs/hypotheses/H-{s}.md").exists())
    df["live SQL"] = df.slug.map(lambda s: (ROOT / f"sql/hypotheses/H-{s}.sql").exists())
    counts = df.status.str.split().str[0].value_counts()
    st.markdown(" ".join(f"<span class='tag'>{k}: {v}</span>" for k, v in counts.items()), unsafe_allow_html=True)
    shown = df.sort_values(["write-up", "live SQL"], ascending=False).reset_index(drop=True)
    picked = st.dataframe(shown, hide_index=True, width="stretch", height=360, on_select="rerun", selection_mode="single-row", key="hypothesis_table")
    st.caption("Select a row above to open a hypothesis.")
    if not (picked and picked.selection.rows):
        return
    slug = shown.slug.iloc[picked.selection.rows[0]]
    used = [n for n, s in strategies_tab.registry()["strategies"].items() if slug in s.get("hypotheses", [])]
    st.markdown(f"### {slug}" + (f" · used by {', '.join(used)}" if used else " · not used by a strategy yet"))
    strategies_tab.hypothesis(slug, strategies_tab.simulator_rows(), expanded=True)
    path = ROOT / f"sql/hypotheses/H-{slug}.sql"
    if not path.exists():
        return
    statements = [s.strip() for s in path.read_text(encoding="utf-8").split(";\n") if s.strip() and not all(l.startswith("--") for l in s.strip().splitlines())]
    titles = [next((l.lstrip("- ") for l in reversed(s.splitlines()) if l.startswith("--")), s[:50]) for s in statements]
    i = st.selectbox("Query to run on live data", range(len(statements)), format_func=titles.__getitem__)
    if st.button("Run live"):
        st.dataframe(q("\n".join(l for l in statements[i].splitlines() if not l.startswith("--")).rstrip(";").replace("{TEAM}", rt.TEAM)), hide_index=True)
    st.code(statements[i], language="sql")


# ---------- 4. explore ----------
def explore():
    e = report("explore")
    if e.empty:
        st.info("No explore rows yet.")
        return
    e["click %"], e["buy %"] = 100 * e.clicks / e.requests, 100 * e.purchases / e.requests
    a, c = st.columns([3, 2])
    a.dataframe(e[["stratum", "requests", "clicks", "purchases", "click %", "buy %", "pool"]], hide_index=True,
                column_config={"click %": PCT, "buy %": PCT, "pool": st.column_config.NumberColumn("mean pool size", format="%.0f")})
    c.altair_chart(alt.Chart(e).mark_bar(color=OKABE[0]).encode(y=alt.Y("stratum:N", title=None, sort="-x"), x=alt.X("click %:Q", title="Click rate per request, %"),
                   tooltip=["stratum", "requests", "clicks"]).properties(height=220), width="stretch")
    st.caption(f"{100 * cfg['explore_share']:.0f}% of shoppers see products drawn at random from one of six groups, with the chance of each draw logged. "
               "This measures what the history log cannot: other categories, favourites, new products. Counts are small, so only large gaps mean anything yet.")


# ---------- 5. backlog and journal ----------
def backlog():
    a, c = st.columns(2)
    a.markdown((ROOT / "docs/backlog/README.md").read_text(encoding="utf-8"))
    journal = (ROOT / "docs/JOURNAL.md").read_text(encoding="utf-8").splitlines()
    c.markdown("# Journal, newest first\n\n" + "\n".join(reversed([l for l in journal if l.startswith("- ")])))


# ---------- 6. raw tables ----------
def raw():
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


# ---------- 7. how it works ----------
def how():
    a, c = st.columns([3, 1])
    a.graphviz_chart("""digraph { rankdir=LR; bgcolor="transparent"; node [shape=box, style="rounded", fontname=Helvetica, color="#8FA3C7", fontcolor="#E6EBF4"];
      edge [fontname=Helvetica, fontsize=10, color="#8FA3C7", fontcolor="#C9D2E3"];
      shoppers -> "shop.requests" -> arm;
      subgraph cluster_router { label="router"; color="#56B4E9"; fontcolor="#56B4E9"; style=rounded;
        state; arm [label="arm choice"]; strategy; guard; state -> strategy; arm -> strategy -> guard; }
      "shop.events" -> state; "shop.catalog_updates" -> state;
      guard -> "submissions" -> simulator; simulator -> "feedback"; simulator -> leaderboard;
      leaderboard -> "block readings"; "feedback" -> "block readings"; "block readings" -> "arms.toml" -> arm [label="hot reload"]; }""", width="stretch")
    c.markdown("### arms.toml now")
    c.markdown(f"- champion: **{champion}**\n- block schedule: {', '.join(cfg['schedule']) or 'champion always'}\n- explore share: {100 * cfg['explore_share']:.0f}%\n"
               + "\n".join(f"- route `{k}`: {', '.join(v) or 'default'}" for k, v in cfg["routes"].items()))
    st.info("The illustrated explanation is `docs/explainer.html`: open it in a browser. It tells the story in ten pictures, with no code.")


for tab, body in zip(tabs, (live, lambda: strategies_tab.render(cfg), overview, one_request, hypotheses, explore, backlog, raw, how)):
    safe(tab, body)

if auto:
    time.sleep(30)
    st.cache_data.clear()
    st.rerun()
