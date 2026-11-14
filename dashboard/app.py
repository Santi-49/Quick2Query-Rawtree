"""quick2query dashboard: how the recommender works, and the live numbers. Read-only.

    uv run --group dashboard streamlit run dashboard/app.py
"""
import importlib
import re
import time
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from q2q import evaluate, rt, serve
from q2q.strategy import Request, decode, guard, load
from q2q.strategies.explore import BASE

ROOT = rt.ROOT
PALETTE = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00"]  # Okabe-Ito
PCT = st.column_config.NumberColumn(format="%.2f%%")

st.set_page_config(page_title="quick2query", layout="wide")
st.title("quick2query · how it works, live")


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


def rate(df: pd.DataFrame, num: str, den: str = "requests") -> pd.Series:
    return 100 * df[num] / df[den].where(df[den] > 0)


with st.sidebar:
    if st.button("Refresh"):
        st.cache_data.clear()
        for _ in range(3):
            live_state().refresh()
    st.caption("Data is cached for 30 s. Everything here only reads RawTree.")

tabs = st.tabs(["How it works", "One live request", "Scoreboard", "Strategies", "Hypotheses", "Explore arm"])

# ---------- 1. How it works ----------
with tabs[0]:
    explainer = ROOT / "docs" / "EXPLAINER.md"
    if explainer.exists():
        st.markdown(explainer.read_text(encoding="utf-8"))
    else:
        st.info("docs/EXPLAINER.md is not written yet.")
    left, right = st.columns([3, 1])
    left.graphviz_chart("""digraph {
  rankdir=LR; node [shape=box, style=rounded, fontname=Helvetica]; edge [fontname=Helvetica, fontsize=10];
  shoppers -> "shop.requests";
  subgraph cluster_router { label="router (serve.py)"; style=rounded;
    state [label="state"]; arm [label="arm choice"]; strategy [label="strategy"]; guard [label="guard"];
    state -> strategy; arm -> strategy -> guard; }
  "shop.requests" -> arm;
  "shop.events" -> state; "shop.catalog_updates" -> state;
  guard -> "team_01.submissions" -> simulator;
  simulator -> "team_01.feedback"; simulator -> leaderboard;
  leaderboard -> "block readings"; "team_01.feedback" -> "block readings";
  "block readings" -> "decision in arms.toml" -> arm [label="hot reload"];
}""", width="stretch")
    try:
        cfg, _ = serve.Arms().get()
        now = time.time()
        if cfg["schedule"]:
            owner = cfg["schedule"][int((now - serve.BLOCK_START) // 600) % len(cfg["schedule"])]
        else:
            owner = cfg["champion"]
        ends = serve.BLOCK_START + (int((now - serve.BLOCK_START) // 600) + 1) * 600
        right.subheader("arms.toml now")
        right.markdown(f"- champion: **{cfg['champion']}**\n- schedule: {', '.join(cfg['schedule']) or '(none: champion always)'}"
                       f"\n- explore share: {100 * cfg['explore_share']:.2f}%")
        right.metric("Arm owning this block", owner, help="Every request outside the explore share goes to this arm.")
        right.caption(f"Block ends at {time.strftime('%H:%M:%S', time.gmtime(ends))} UTC.")
    except Exception as e:
        right.warning(f"arms.toml could not be read: {e}")

# ---------- 2. One live request ----------
with tabs[1]:
    try:
        reqs = rt.query(serve.POLL.replace("LIMIT 60", "LIMIT 30"))
        if not reqs:
            st.info("No requests in shop.requests yet.")
        else:
            state = live_state()
            labels = [f"{time.strftime('%H:%M:%S', time.gmtime(r['ts_ms'] / 1000))} · {r['page']} · {r['device']} · {r['region']} · "
                      f"{'new' if r['is_new_user'] else 'returning'} · {len(r['views'])} views" for r in reqs]
            i = st.selectbox("Request (newest first)", range(len(reqs)), format_func=labels.__getitem__)
            r = reqs[i]
            req = Request(r["request_id"], r["ts_ms"] / 1000, r["user_id"], bool(r["is_new_user"]),
                          r["page"], r["device"], r["region"], list(r["views"]))
            P = state.products
            shopper = state.shopper(req.user_id)
            st.subheader("The shopper")
            c = st.columns(4)
            c[0].metric("Known from history or today", "yes" if shopper else "no")
            c[1].metric("Products bought", len(shopper.bought) if shopper else 0)
            c[2].metric("Products viewed before, not bought", len(shopper.viewed) if shopper else 0)
            top = sorted(shopper.cat_share.items(), key=lambda kv: -kv[1])[:3] if shopper else []
            c[3].markdown("**Favourite categories**\n\n" + ("\n".join(f"- {k}: {100 * v:.2f}%" for k, v in top) or "none"))
            lifts = {k: v for k, v in state.segment.get((req.device, req.region), {}).items() if v > 1.5}
            st.caption(f"Segment {req.device} × {req.region}: " + (", ".join(f"{k} ×{v:.1f}" for k, v in sorted(lifts.items(), key=lambda kv: -kv[1]))
                                                                     or "no category above ×1.5"))
            st.markdown("**Recent views** (oldest first)")
            if req.views:
                st.dataframe(pd.DataFrame([{"subcategory": P[p].subcategory if p in P else "?", "brand": P[p].brand if p in P else "?",
                                            "price €": P[p].price if p in P else None, "in stock": state.available(p)} for p in req.views]),
                             hide_index=True, column_config={"price €": st.column_config.NumberColumn(format="%.2f")})
            else:
                st.caption("No recent views: the strategies fall back on the shopper's history and the segment.")
            subs = {P[p].subcategory for p in req.views if p in P}
            cats = {P[p].category for p in req.views if p in P}

            def mark(p):
                return "viewed" if p in req.views else "same subcategory" if P[p].subcategory in subs else "same category" if P[p].category in cats else ""

            def table(items):
                return pd.DataFrame([{"#": k + 1, "subcategory": P[p].subcategory, "brand": P[p].brand, "price €": P[p].price, "link to views": mark(p)}
                                     for k, p in enumerate(items)])
            cols = st.columns(3)
            for col, name in zip(cols, ["baseline", "rules", "explore"]):
                strat = load(name)
                items = guard(strat.recommend(req, state), state)
                col.markdown(f"**{name}**")
                col.dataframe(table(items), hide_index=True, column_config={"price €": st.column_config.NumberColumn(format="%.2f")})
                if name == "rules":
                    rows = [{"product": P[p].subcategory, "score": s, **{k: round(v, 3) for k, v in parts.items()}} for s, p, parts in strat.explain(req, state)]
                    if rows:
                        col.dataframe(pd.DataFrame(rows), hide_index=True, column_config={"score": st.column_config.NumberColumn(format="%.4f")})
                    src = (ROOT / "src/q2q/strategies/rules.py").read_text(encoding="utf-8")
                    note = dict(re.findall(r"^([A-Z_]+)\s*=.*?#\s*(.+)$", src, re.M))
                    from q2q import state as state_mod
                    captions = {"appeal": state_mod.appeal.__doc__, "session": f"Last view: {note.get('LAST_VIEW', '')}; other recent view; same subcategory, then category.",
                                "viewed before": f"History views of a product not bought: {note.get('VIEWED_BEFORE', '')}.",
                                "favourite category": f"1 + weight × the shopper's share of views in the category: {note.get('SHARE_HOME', '')}.",
                                "segment": state_mod.segment_from.__doc__, "trend": state_mod.trend_from.__doc__,
                                "price cut": "2 minus the new price over the starting price, so a 20% cut gives ×1.2."}
                    col.caption("\n\n".join(f"**{k}**: {v}" for k, v in captions.items()))
                if name == "explore":
                    col.caption(f"Stratum drawn: **{req.log.get('stratum')}**, propensity {req.log.get('propensity', 0):.4f} "
                                f"(stratum probability {req.log.get('p_stratum', 0):.2f}, pool of {req.log.get('pool', 0)}).")
            st.caption("This page runs the strategies again on the state held by the dashboard, so the answers can differ slightly from what the router sent.")
    except Exception as e:
        st.warning(f"Could not show a live request: {e}")

# ---------- 3. Scoreboard ----------
arm_scores: dict[str, float] = {}
with tabs[2]:
    try:
        b = blocks()
        if b.empty or b["score"].isna().all():
            st.info(f"No block with a known lift since {evaluate.START} UTC yet. The first appears one leaderboard refresh after a full block.")
        else:
            b["arm"] = b["arm"].str.split("@").str[0]
            scored = b.dropna(subset=["score"])
            bars = alt.Chart(scored).mark_bar().encode(
                x=alt.X("block_end:N", title="block end (UTC)"), y=alt.Y("score:Q", title="score on the block (100 = oracle)"),
                color=alt.Color("arm:N", scale=alt.Scale(range=PALETTE), title="arm"), tooltip=["block_end", "arm", alt.Tooltip("score", format=".1f")])
            ref = alt.Chart(b.dropna(subset=["ref_window_score"])).mark_line(point=True, color="#555").encode(
                x="block_end:N", y="ref_window_score:Q", tooltip=["block_end", alt.Tooltip("ref_window_score", title="reference, hourly", format=".1f")])
            st.altair_chart(bars + ref, width="stretch")
            st.caption("Bars: our score per 10-minute block, by arm. Grey line: the reference team's score over the hourly leaderboard window.")
            arms = pd.DataFrame(evaluate.by_arm(b.to_dict("records")))
            arm_scores = dict(zip(arms["arm"], arms["score"]))
            arms["click_rate"] *= 100
            st.dataframe(arms, hide_index=True, column_config={"score": st.column_config.NumberColumn("mean score", format="%.1f"),
                                                               "se": st.column_config.NumberColumn("standard error", format="%.1f"), "click_rate": PCT})
            st.caption("Two hourly windows ten minutes apart differ by one block entering and one leaving, so the change in our purchases minus the baseline's, "
                       "plus the reading for the block that just left, is our lift on the new block. "
                       f"That lift as a share of the gap between oracle and baseline ({evaluate.ORACLE_GAP} points) is the block score.")
            show = b[["block_end", "arm", "requests", "score", "click_rate", "window_score", "ref_window_score"]].copy()
            show["click_rate"] *= 100
            st.dataframe(show.iloc[::-1], hide_index=True, column_config={"click_rate": PCT, "score": st.column_config.NumberColumn(format="%.1f"),
                         "window_score": st.column_config.NumberColumn(format="%.1f"), "ref_window_score": st.column_config.NumberColumn(format="%.1f")})
    except Exception as e:
        st.warning(f"Block readings failed: {e}")
    st.subheader("Reliability, last 3 hours")
    try:
        rel = report("reliability")
        if rel.empty:
            st.info("No feedback rows in the last 3 hours.")
        else:
            rel["answered %"] = rate(rel, "answered")
            rel["time"] = pd.to_datetime(rel["t"])
            c1, c2 = st.columns(2)
            c1.altair_chart(alt.Chart(rel).mark_line(point=True).encode(x=alt.X("time:T", title="10 minutes starting (UTC)"),
                            y=alt.Y("answered %:Q", title="answered by us (%)")), width="stretch")
            lat = rel.melt("time", ["p50_ms", "p95_ms"], "quantile", "ms").dropna()
            c2.altair_chart(alt.Chart(lat).mark_line(point=True).encode(x=alt.X("time:T", title="10 minutes starting (UTC)"), y=alt.Y("ms:Q", title="latency (ms)"),
                            color=alt.Color("quantile:N", scale=alt.Scale(range=PALETTE), title="")), width="stretch")
            st.dataframe(rel[["t", "requests", "answered %", "missing", "late", "invalid", "p50_ms", "p95_ms"]].iloc[::-1], hide_index=True,
                         column_config={"answered %": PCT})
    except Exception as e:
        st.warning(f"Reliability query failed: {e}")

# ---------- 4. Strategies ----------
with tabs[3]:
    try:
        live = report("strategies")
        if not live.empty:
            live["click rate"], live["purchase rate"] = rate(live, "clicks"), rate(live, "purchases")
            live["strategy"] = live["strategy"].map(decode)
            live = live.groupby("strategy", as_index=False).agg({c: ("min" if live[c].dtype == object else "sum") for c in live.columns if c != "strategy"})
            live["click rate"], live["purchase rate"] = rate(live, "clicks"), rate(live, "purchases")
            live = live.set_index("strategy")
    except Exception as e:
        live = pd.DataFrame()
        st.warning(f"Live strategy numbers failed: {e}")
    for f in sorted((ROOT / "src/q2q/strategies").glob("*.py")):
        if f.stem == "__init__":
            continue
        with st.expander(f.stem, expanded=True):
            st.markdown(importlib.import_module(f"q2q.strategies.{f.stem}").__doc__ or "(no docstring)")
            if f.stem in live.index:
                row = live.loc[f.stem]
                c = st.columns(5)
                c[0].metric("Requests with feedback", f"{int(row['requests']):,}")
                c[1].metric("Click rate", f"{row['click rate']:.2f}%")
                c[2].metric("Purchase rate", f"{row['purchase rate']:.2f}%")
                c[3].metric("Since (UTC)", row["since"][:16])
                c[4].metric("Mean block score", f"{arm_scores[f.stem]:.1f}" if f.stem in arm_scores else "no blocks")
            else:
                st.caption("Not served live yet.")

# ---------- 5. Hypotheses ----------
with tabs[4]:
    def md_table(text: str, heading: str) -> pd.DataFrame:
        part = text.split(heading, 1)[1].split("\n## ", 1)[0] if heading in text else ""
        rows = [[c.strip().replace("**", "") for c in line.strip().strip("|").split("|")] for line in part.splitlines() if line.startswith("|")]
        rows = [r for r in rows if not set("".join(r)) <= set("-: ")]
        return pd.DataFrame(rows[1:], columns=rows[0]) if rows else pd.DataFrame()

    try:
        sim = (ROOT / "docs" / "SIMULATOR.md").read_text(encoding="utf-8")
        verdicts, new = md_table(sim, "## Verdicts on the first hypotheses"), md_table(sim, "## New hypotheses")
        words = [v.split()[0].strip(",") for v in verdicts.get("Verdict", [])] + ["open"] * len(new)
        counts = pd.Series(words).value_counts()
        c = st.columns(4)
        for col, w in zip(c, ["confirmed", "likely", "weak", "open"]):
            col.metric(w, int(counts.get(w, 0)))
        st.markdown("**Verdicts on the first hypotheses**")
        st.dataframe(verdicts, hide_index=True)
        st.markdown("**New hypotheses** (open)")
        st.dataframe(new, hide_index=True)
    except Exception as e:
        st.warning(f"docs/SIMULATOR.md could not be parsed: {e}")
    files = sorted((ROOT / "docs" / "hypotheses").glob("H-*.md"))
    if not files:
        st.info("No hypothesis files yet (docs/hypotheses/H-<slug>.md). Each new test gets one, with its SQL in sql/hypotheses/.")
    for f in files:
        with st.expander(f.stem):
            st.markdown(f.read_text(encoding="utf-8"))
            sql = ROOT / "sql" / "hypotheses" / f"{f.stem}.sql"
            if sql.exists() and st.button("Run live", key=f.stem):
                try:
                    st.dataframe(q(sql.read_text(encoding="utf-8")), hide_index=True)
                except Exception as e:
                    st.warning(f"{sql.name} failed: {e}")

# ---------- 6. Explore arm ----------
with tabs[5]:
    st.caption(f"The explore arm takes a small share of shoppers and shows products the champion would not, drawn at random from one of {len(BASE)} groups, "
               "to measure what the old carousel's log cannot. Counts are small: read them as direction, not proof.")
    try:
        ex = report("explore")
        if ex.empty:
            st.info("No explore rows with feedback yet (team_01.scratch, kind = 'explore').")
        else:
            ex["click rate"], ex["purchase rate"] = rate(ex, "clicks"), rate(ex, "purchases")
            st.dataframe(ex[["stratum", "requests", "click rate", "purchase rate", "pool"]], hide_index=True,
                         column_config={"click rate": PCT, "purchase rate": PCT, "pool": st.column_config.NumberColumn("mean pool size", format="%.1f")})
    except Exception as e:
        st.warning(f"Explore query failed: {e}")
