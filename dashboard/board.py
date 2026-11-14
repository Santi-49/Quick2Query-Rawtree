"""The Board tab: strategies and hypotheses as cards in three columns (tested, testing now, up next),
one chart of the score per 15-minute window, and the detail dialog that a card's "Details" button opens.
"""
from html import escape

import altair as alt
import pandas as pd
import streamlit as st

import data
import ui
from q2q import rt
from q2q.strategy import label

WINDOWS = {15: "15 min", 30: "30 min", 60: "1 h", 180: "3 h"}
COLUMNS = (("tested", "Tested", "done, with a result"), ("testing", "Testing now", "running"), ("next", "Up next", "not started"))
FEW = 300  # under this many requests a score is a rough reading


def window() -> int:
    return st.session_state.get("window") or 60


def open_detail(kind: str, key: str) -> None:
    """Ask for a detail dialog. The page opens it on the full rerun that follows."""
    st.session_state["detail"] = (kind, key)
    st.rerun()


def columns(groups: dict[str, list], draw, shown: int, noun: str) -> None:
    """Three columns of cards; beyond `shown` cards the rest of a column sits in an expander."""
    for col, (group, title, hint) in zip(st.columns(3, gap="medium"), COLUMNS):
        with col:
            items = groups.get(group, [])
            ui.column_title(title, len(items), hint)
            if not items:
                ui.html(f'<div class="empty">No {noun} here.</div>')
            for item in items[:shown]:
                draw(item)
            if len(items) > shown:
                with st.expander(f"{len(items) - shown} more"):
                    for item in items[shown:]:
                        draw(item)


# ---------- strategy cards ----------
def score_rows(s: dict, b: pd.DataFrame, champion: str) -> str:
    """Score per kind of request in the window, next to the champion on the same kind of request."""
    mine = b[b.arm == s["name"]]
    if mine.empty:
        return ""
    is_champion = s["name"] == champion
    head = "conversion" if is_champion else "vs champion"
    rows = ""
    for route in data.ROUTES:
        r = mine[mine.route == route]
        if r.empty:
            continue
        r = r.iloc[0]
        champ = b[(b.arm == champion) & (b.route == route)]
        if is_champion:
            last = f"{r.conversion:.2f}%"
        elif champ.empty:
            last = "no champion here"
        else:
            last = f"{r.score - champ.score.iloc[0]:+.1f}"
        kind = "all kinds" if s["name"] == "explore" else data.ROUTES[route]
        few = " <small>· few</small>" if r.requests < FEW else ""
        rows += f'<tr title="{int(r.requests):,} requests"><td>{kind}{few}</td><td class="sc">{r.score:+.1f}</td><td class="vs">{last}</td></tr>'
    return f'<table class="rt"><tr><th>requests</th><th>score</th><th>{head}</th></tr>{rows}</table>'


def strategy_card(s: dict, b: pd.DataFrame, share: dict, champion: str) -> None:
    with st.container(border=True, key=f"card_s_{s['name']}"):
        body = (f'<div class="ch"><span class="nm">{escape(s["public"])}</span>{ui.tag(s["tag"])}</div>'
                f'<div class="sub">internal name {escape(s["name"])}</div>'
                f'<p class="desc">{escape(data.brief(s["summary"]))}</p>')
        if s["group"] == "testing":
            body += ui.share_bar(share.get(s["name"], 0.0)) + score_rows(s, b, champion)
        elif s["group"] == "tested":
            body += score_rows(s, b, champion)
            if s["conclusion"]:
                body += f'<p class="note"><b>Result.</b> {escape(data.brief(s["conclusion"]))}</p>'
        ui.html(f'<div class="cb">{body}</div>')
        if st.button("Details", key=f"open_s_{s['name']}", help=f"Open {s['public']}"):
            open_detail("strategy", s["name"])


def idea_card(i: int, idea: dict) -> None:
    with st.container(border=True, key=f"card_i_{i}"):
        ui.html(f'<div class="cb"><div class="ch"><span class="nm plain">{escape(str(idea.get("idea", "Idea")))}</span>{ui.tag("Idea")}</div>'
                f'<div class="sub">not built yet · size {escape(str(idea.get("size", "unknown")))}</div>'
                f'<p class="desc">{escape(data.brief(idea.get("why", "")))}</p></div>')
        if idea.get("hypothesis") and st.button("Hypothesis behind it", key=f"open_i_{i}"):
            open_detail("hypothesis", idea["hypothesis"])


# ---------- hypothesis cards ----------
def nice(slug: str) -> str:
    return slug.replace("-", " ")


def hypothesis_card(h: dict) -> None:
    with st.container(border=True, key=f"card_h_{h['slug']}"):
        line = (h["verdict"] if h["text"] else h["consequence"]) if h["group"] == "tested" else h["claim"]
        users = ", ".join(label(n) for n in h["used_by"])
        ui.html(f'<div class="cb"><div class="ch"><span class="nm plain">{escape(nice(h["slug"]))}</span>{ui.tag(h["kind"])}</div>'
                + (f'<div class="sub">used by {escape(users)}</div>' if users else "")
                + (f'<p class="note">{escape(data.brief(line))}</p>' if line else "") + "</div>")
        if st.button("Details", key=f"open_h_{h['slug']}", help=f"Open {h['slug']}"):
            open_detail("hypothesis", h["slug"])


# ---------- the one chart ----------
def trend(hist: pd.DataFrame, cfg: dict) -> None:
    left, right = st.columns([3, 2], vertical_alignment="bottom")
    left.markdown("### Score per 15-minute window")
    route = right.radio("Kind of request", list(data.ROUTES), format_func=data.ROUTES.get, horizontal=True, key="trend_route", label_visibility="collapsed")
    h = hist[(hist.route == route) & (hist.requests >= 100) & hist.arm.isin(data.running(cfg))].copy() if not hist.empty else hist
    if h.empty:
        st.info("No leaderboard reading for this kind of request in the last two hours.")
        return
    h = h.sort_values("window_end")
    h["time"] = h.window_end.str[11:16]
    h["strategy"] = h.arm.map(lambda a: f"{label(a)} (champion)" if a == cfg["champion"] else label(a))
    order = sorted(h.strategy.unique(), key=lambda s: ("(champion)" not in s, s))
    base = alt.Chart(h).encode(x=alt.X("time:N", title="Window ending (UTC)", sort=list(h.time.unique()), axis=alt.Axis(labelAngle=0)))
    lines = base.mark_line(strokeWidth=2.5, point=alt.OverlayMarkDef(size=70, filled=True)).encode(
        y=alt.Y("score:Q", title="Score"),
        color=alt.Color("strategy:N", sort=order, scale=alt.Scale(domain=order, range=ui.SERIES[:len(order)]), legend=alt.Legend(orient="top", title=None, symbolType="stroke")),
        strokeDash=alt.StrokeDash("strategy:N", sort=order, legend=None), shape=alt.Shape("strategy:N", sort=order, legend=None),
        tooltip=[alt.Tooltip("strategy:N"), alt.Tooltip("time:N", title="window ending"), alt.Tooltip("score:Q", format="+.1f"),
                 alt.Tooltip("conversion:Q", format=".2f", title="conversion %"), alt.Tooltip("requests:Q", format=",")])
    st.altair_chart(lines.properties(height=260).configure_axis(gridColor="#222C42", domainColor=ui.BORDER, labelColor=ui.MUTED, titleColor=ui.MUTED)
                    .configure_view(strokeWidth=0).configure_legend(labelColor=ui.TEXT), width="stretch")
    st.caption(f"Strategies answering {data.ROUTES[route]} requests ({data.ROUTE_HELP[route]}) at the same time on separate shoppers, so lines compare directly. "
               "Only strategies that have traffic now; windows with under 100 requests are left out.")


# ---------- the tab ----------
@st.fragment(run_every=30)
def render() -> None:
    cfg, reg = data.arms(), data.registry()
    top = st.columns([2, 3, 4], vertical_alignment="center")
    top[0].markdown("### Strategies")
    minutes = top[1].radio("Scores over the last", list(WINDOWS), index=2, format_func=lambda m: "last " + WINDOWS[m], horizontal=True, key="window", label_visibility="collapsed")
    try:
        b = data.board(minutes)
    except Exception as e:
        b = data._per_route([])
        st.warning(f"The per-model leaderboard did not answer, so cards show no scores: {e}")
    try:
        share = data.shares(data.live())
    except Exception as e:
        share = {}
        st.warning(f"Live traffic could not be read: {e}")
    reading = f"leaderboard window to {b.window_end.iloc[0][11:16]}" if len(b) else "no leaderboard reading"
    top[2].markdown(f'<div class="stamp" style="text-align:right">updated {data.stamp()} · {reading} · refreshes every 30 s</div>', unsafe_allow_html=True)

    items = data.strategies(cfg, reg)
    rank = lambda s: (s["name"] != cfg["champion"], s["name"] == "explore", -share.get(s["name"], 0))
    groups = {g: sorted((s for s in items if s["group"] == g), key=rank) for g in data.GROUPS}
    cards = {g: [("s", s) for s in groups[g]] for g in data.GROUPS}
    cards["next"] += [("i", (i, idea)) for i, idea in enumerate(reg["backlog"])]
    columns(cards, lambda c: strategy_card(c[1], b, share, cfg["champion"]) if c[0] == "s" else idea_card(*c[1]), shown=4, noun="strategies")
    st.caption("Score: 0 is the organisers' baseline, 100 the hidden model's own picks. A score is read on one kind of request "
               "(ordinary, new shopper, no recent views); \"vs champion\" compares with the champion on the same kind of request over the same minutes.")

    try:
        trend(data.history(), cfg)
    except Exception as e:
        st.warning(f"The score history could not be read: {e}")

    st.markdown("### Hypotheses about the simulator")
    hyps = data.hypotheses(reg, cfg)
    columns({g: [h for h in hyps if h["group"] == g] for g in data.GROUPS}, hypothesis_card, shown=3, noun="hypotheses")


# ---------- details ----------
def hypothesis_body(h: dict, with_sql: bool = True) -> None:
    for name in ("claim", "verdict", "evidence", "consequence", "test"):
        if h[name]:
            st.markdown(f"**{name.capitalize()}.** {h[name]}")
    if not (h["claim"] or h["verdict"] or h["text"]):
        st.caption("Nothing written yet: it is only named by a strategy or a backlog idea.")
    if h["used_by"]:
        st.markdown("**Used by.** " + ", ".join(f"{label(n)} ({n})" for n in h["used_by"]))
    if h["ideas"]:
        st.markdown("**Backlog ideas that rest on it.** " + "; ".join(h["ideas"]))
    if h["text"]:
        with st.expander("Full write-up"):
            st.markdown(h["text"])
    queries = data.statements(h["slug"]) if with_sql else []
    if queries:
        with st.expander("Run its queries on live data"):
            i = st.selectbox("Query", range(len(queries)), format_func=lambda k: queries[k][0], key=f"sql_pick_{h['slug']}")
            if st.button("Run live", key=f"sql_run_{h['slug']}"):
                try:
                    sql = "\n".join(l for l in queries[i][1].splitlines() if not l.startswith("--")).rstrip(";")
                    st.dataframe(data.q(sql.replace("{TEAM}", rt.TEAM)), hide_index=True)
                except Exception as e:
                    st.warning(f"The query failed: {e}")
            st.code(queries[i][1], language="sql")


def strategy_detail(name: str) -> None:
    cfg, reg = data.arms(), data.registry()
    s = next((x for x in data.strategies(cfg, reg) if x["name"] == name), None)
    if s is None:
        st.info("This strategy is no longer listed.")
        return
    ui.html(f'<div class="ch"><span class="nm">{escape(s["public"])}</span>{ui.tag(s["tag"])}</div><div class="sub">internal name {escape(name)}</div>')
    st.markdown(s["summary"])
    if s["conclusion"]:
        st.markdown(f"**Conclusion so far.** {s['conclusion']}")
    if not s["registered"]:
        st.caption("Not in strategies.toml yet: the description is the first paragraph of its file.")
    if s["group"] != "next":
        minutes = window()
        try:
            b = data.board(minutes)
        except Exception as e:
            b = data._per_route([])
            st.warning(f"The per-model leaderboard did not answer: {e}")
        mine = b[b.arm == name]
        if mine.empty:
            st.info(f"No leaderboard reading in the last {WINDOWS[minutes]} (it lists a model from 100 requests). Its result is the conclusion above.")
        else:
            champ = b[b.arm == cfg["champion"]].set_index("route").score
            table = pd.DataFrame({"kind of request": mine.route.map(data.ROUTES), "public name": mine.labels, "requests": mine.requests,
                                  "conversion %": mine.conversion, "score": mine.score,
                                  "champion, same requests": mine.route.map(champ) if name != cfg["champion"] else float("nan")})
            table["difference"] = table.score - table["champion, same requests"]
            number = lambda f: st.column_config.NumberColumn(format=f)
            st.dataframe(table.dropna(axis=1, how="all"), hide_index=True, column_config={"conversion %": number("%.2f%%"), "score": number("%+.1f"),
                         "champion, same requests": number("%+.1f"), "difference": number("%+.1f"), "requests": number("localized")})
            st.caption(f"Last {WINDOWS[minutes]}, window to {mine.window_end.iloc[0][11:16]} UTC. Baseline {mine.baseline.iloc[0]:.2f}%, reference {mine.reference.iloc[0]:.2f}% over all requests. "
                       "Rows are different kinds of request: compare a row only with the champion's score on the same kind.")
    if s["group"] == "testing":
        try:
            df = data.live()
            got = df[df.strategy == name].route.value_counts()
            parts = [f"{data.ROUTES[r]} {100 * got.get(r, 0) / max((df.route == r).sum(), 1):.0f}%" for r in data.ROUTES if got.get(r, 0)]
            st.markdown(f"**Live traffic, last 5 minutes.** {100 * got.sum() / max(len(df), 1):.0f}% of all requests" + (": " + ", ".join(parts) + " of each kind." if parts else "."))
        except Exception as e:
            st.caption(f"Live traffic could not be read: {e}")
    if name == "explore":
        with st.expander("What the explore arm has measured, per group of products"):
            try:
                e = data.report("explore")
                e["click %"], e["buy %"] = 100 * e.clicks / e.requests, 100 * e.purchases / e.requests
                st.dataframe(e[["stratum", "requests", "clicks", "purchases", "click %", "buy %"]], hide_index=True,
                             column_config={"click %": st.column_config.NumberColumn(format="%.2f%%"), "buy %": st.column_config.NumberColumn(format="%.2f%%")})
            except Exception as err:
                st.caption(f"No explore rows could be read: {err}")
    if s["hypotheses"]:
        st.markdown("**Built on these hypotheses**")
        known = {h["slug"]: h for h in data.hypotheses(reg, cfg)}
        for slug in s["hypotheses"]:
            h = known.get(slug)
            with st.expander(f"{nice(slug)} · {ui.WORDS[h['kind']].lower() if h else 'not written yet'}"):
                if h:
                    hypothesis_body(h, with_sql=False)
    if s["has_file"]:
        with st.expander("Source code"):
            st.code(data.source(name), language="python")


def hypothesis_detail(slug: str) -> None:
    h = next((x for x in data.hypotheses(data.registry(), data.arms()) if x["slug"] == slug), None)
    if h is None:
        st.info("Nothing is written about this hypothesis yet.")
        return
    state = {"tested": "Tested", "testing": "Testing now", "next": "Up next"}[h["group"]]
    ui.html(f'<div class="ch"><span class="nm plain">{escape(h["title"] or nice(slug))}</span>{ui.tag(h["kind"])}</div><div class="sub">{state} · {escape(slug)}</div>')
    hypothesis_body(h)


def show_pending() -> None:
    """Open the dialog a card asked for. Called once per full run; the request is consumed, so closing it sticks."""
    target = st.session_state.pop("detail", None)
    if not target:
        return
    kind, key = target
    title = f"Strategy · {label(key)}" if kind == "strategy" else f"Hypothesis · {nice(key)}"
    st.dialog(title, width="large")(strategy_detail if kind == "strategy" else hypothesis_detail)(key)
