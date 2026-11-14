"""The Now and Strategies tabs, the hypothesis cards, and the detail dialog that a card's "Details" button opens.

Scores are always read per kind of request (ordinary, new shopper, no recent views): arms on the same kind saw
the same shoppers at the same time, so only those compare.
"""
from html import escape

import altair as alt
import pandas as pd
import streamlit as st

import data
import ui
from q2q import rt

WINDOWS = {15: "15 min", 30: "30 min", 60: "1 h", 180: "3 h"}
COLUMNS = (("tested", "Tested", "done, with a result"), ("testing", "Testing now", "has live traffic"), ("next", "Up next", "not started, no score yet"))
FEW = 300  # under this many requests a score is a rough reading


def guarded(body):
    """A tab body that shows a warning instead of breaking the page; it tries again on its next refresh."""
    def run(*args, **kwargs):
        try:
            body(*args, **kwargs)
        except Exception as e:
            st.warning(f"This view could not be built: {e}")
    run.__name__ = body.__name__
    return run


def open_detail(kind: str, key: str) -> None:
    """Ask for a detail dialog. The page opens it on the full rerun that follows."""
    st.session_state["detail"] = (kind, key)
    st.rerun()


def read_board(minutes: int) -> pd.DataFrame:
    try:
        return data.board(minutes)
    except Exception as e:
        st.warning(f"The per-model leaderboard did not answer, so no scores are shown: {e}")
        return data._per_route([])


def read_live() -> pd.DataFrame:
    try:
        return data.live()
    except Exception as e:
        st.warning(f"Live traffic could not be read: {e}")
        return pd.DataFrame()


def title(text: str, note: str) -> None:
    left, right = st.columns([2, 3], vertical_alignment="bottom")
    left.markdown(f"### {text}")
    right.markdown(f'<div class="stamp" style="text-align:right">{note}</div>', unsafe_allow_html=True)


def few(requests: float) -> str:
    return ' <small title="under 300 requests: a rough reading">· few</small>' if requests < FEW else ""


def columns(groups: dict[str, list], draw, shown: int, noun: str) -> None:
    """Three columns of cards; beyond `shown` cards the rest of a column sits in an expander."""
    for col, (group, name, hint) in zip(st.columns(3, gap="medium"), COLUMNS):
        with col:
            items = groups.get(group, [])
            ui.column_title(name, len(items), hint)
            if not items:
                ui.html(f'<div class="empty">No {noun} here.</div>')
            for item in items[:shown]:
                draw(item)
            if len(items) > shown:
                with st.expander(f"{len(items) - shown} more"):
                    for item in items[shown:]:
                        draw(item)


# ---------- Now ----------
def verdict(rows: list[dict], champion: str) -> str:
    """One sentence per kind of request: who is ahead, by how much."""
    read = sorted((r for r in rows if r["score"] is not None), key=lambda r: -r["score"])
    if len(read) < 2:
        return "One strategy answers these requests, so there is nothing to compare." if len(rows) < 2 else "Not enough requests in this window to compare."
    champ = next((r for r in read if r["name"] == champion), None)
    a, b = (max((r for r in read if r is not champ), key=lambda r: r["score"]), champ) if champ else (read[0], read[1])
    gap = a["score"] - b["score"]
    rough = " <small>· few requests, a rough reading</small>" if min(a["requests"], b["requests"]) < FEW else ""
    who = "the champion" if champ else f'<b style="text-transform:capitalize">{escape(b["public"])}</b>'
    return f'<b style="text-transform:capitalize">{escape(a["public"])}</b> is {abs(gap):.1f} points {"ahead of" if gap >= 0 else "behind"} {who}{rough}'


def route_card(route: str, cfg: dict, b: pd.DataFrame, seen: dict, mix: float | None) -> None:
    plan = data.planned(cfg)[route]
    rows = []
    for name in (n for n in plan if n != "explore"):
        r = b[(b.arm == name) & (b.route == route)]
        rows.append({"name": name, "public": data.label(name), "share": seen.get(name), "plan": plan[name],
                     "score": r.score.iloc[0] if len(r) else None, "conversion": r.conversion.iloc[0] if len(r) else None,
                     "requests": r.requests.iloc[0] if len(r) else 0})
    rows.sort(key=lambda r: (r["score"] is None, -(r["score"] or 0)))
    body = ""
    for r in rows:
        mark = " · champion" if r["name"] == cfg["champion"] else ""
        share = ui.mini(r["share"]) if r["share"] is not None else f'{r["plan"]:.0f}% <small>planned</small>'
        if r["score"] is None:
            body += f'<tr><td><b>{escape(r["public"])}</b> <small>{escape(r["name"])}{mark}</small></td><td>{share}</td><td colspan="3"><small>no reading yet (needs 100 requests)</small></td></tr>'
        else:
            body += (f'<tr><td><b>{escape(r["public"])}</b> <small>{escape(r["name"])}{mark}</small></td><td>{share}</td>'
                     f'<td class="sc">{r["score"]:+.1f}</td><td>{r["conversion"]:.2f}%</td><td>{int(r["requests"]):,}{few(r["requests"])}</td></tr>')
    with st.container(border=True, key=f"card_now_{route}"):
        ui.html(f'<div class="cb solo"><div class="ch"><span class="nm">{data.ROUTES[route]}</span>'
                f'<span class="stamp">{f"{mix:.0f}% of all requests" if mix is not None else ""}</span></div>'
                f'<div class="sub">{data.ROUTE_HELP[route]}</div>'
                f'<table class="rt"><tr><th>strategy</th><th>traffic</th><th>score</th><th>conversion</th><th>requests</th></tr>{body}</table>'
                f'<p class="lead">{verdict(rows, cfg["champion"])}</p></div>')


def trend(hist: pd.DataFrame, cfg: dict) -> None:
    left, right = st.columns([3, 2], vertical_alignment="bottom")
    left.markdown("### Is the lead steady? Score per 15-minute window")
    route = right.radio("Kind of request", list(data.ROUTES), format_func=data.ROUTES.get, horizontal=True, key="trend_route", label_visibility="collapsed")
    names = [n for n in data.planned(cfg)[route] if n != "explore"]
    h = hist[(hist.route == route) & (hist.requests >= 100) & hist.arm.isin(names)].copy() if not hist.empty else hist
    if h.empty:
        st.info("No leaderboard reading for this kind of request in the last two hours.")
        return
    h = h.sort_values("window_end")
    h["time"] = h.window_end.str[11:16]
    h["strategy"] = h.arm.map(lambda a: data.label(a).capitalize() + (" (champion)" if a == cfg["champion"] else ""))
    order = sorted(h.strategy.unique(), key=lambda s: ("(champion)" not in s, s))
    lines = alt.Chart(h).mark_line(strokeWidth=2.5, point=alt.OverlayMarkDef(size=70, filled=True)).encode(
        x=alt.X("time:N", title="Window ending (UTC)", sort=list(h.time.unique()), axis=alt.Axis(labelAngle=0)),
        y=alt.Y("score:Q", title="Score", scale=alt.Scale(zero=False)),
        color=alt.Color("strategy:N", sort=order, scale=alt.Scale(domain=order, range=ui.SERIES[:len(order)]), legend=alt.Legend(orient="top", title=None, symbolType="stroke")),
        strokeDash=alt.StrokeDash("strategy:N", sort=order, legend=None), shape=alt.Shape("strategy:N", sort=order, legend=None),
        tooltip=[alt.Tooltip("strategy:N"), alt.Tooltip("time:N", title="window ending"), alt.Tooltip("score:Q", format="+.1f"),
                 alt.Tooltip("conversion:Q", format=".2f", title="conversion %"), alt.Tooltip("requests:Q", format=",")])
    st.altair_chart(lines.properties(height=240).configure_axis(gridColor="#222C42", domainColor=ui.BORDER, labelColor=ui.MUTED, titleColor=ui.MUTED)
                    .configure_view(strokeWidth=0).configure_legend(labelColor=ui.TEXT), width="stretch")
    st.caption(f"A challenger is promoted when it beats the champion in two 30-minute windows in a row, so one good window is not enough. "
               f"Strategies answering {data.ROUTES[route]} requests now; windows with under 100 requests are left out.")


@st.fragment(run_every=30)
@guarded
def now() -> None:
    cfg = data.arms()
    top = st.columns([3, 3, 4], vertical_alignment="center")
    top[0].markdown("### Running now, by kind of request")
    minutes = top[1].radio("Scores over the last", list(WINDOWS), index=2, format_func=lambda m: "last " + WINDOWS[m], horizontal=True, key="window", label_visibility="collapsed")
    b, df = read_board(minutes), read_live()
    reading = f"leaderboard window to {b.window_end.max()[11:16]}" if len(b) else "no leaderboard reading"
    top[2].markdown(f'<div class="stamp" style="text-align:right">updated {data.stamp()} · {reading} · traffic of the last 5 min · refreshes every 30 s</div>', unsafe_allow_html=True)
    seen = data.observed(df)
    for col, route in zip(st.columns(3, gap="medium"), data.ROUTES):
        with col:
            route_card(route, cfg, b, seen[route], 100 * (df.route == route).mean() if len(df) else None)
    notes = []
    if len(b):
        notes.append(f"Score 0 is the organisers' baseline ({b.baseline.iloc[-1]:.2f}% conversion), 100 the hidden model's own picks; "
                     f"their reference recommender is at {100 * (b.reference.iloc[-1] - b.baseline.iloc[-1]) / data.evaluate.ORACLE_GAP:+.1f} over all kinds of request.")
    e = b[b.arm == "explore"]
    if cfg.get("explore_share", 0) > 0:
        notes.append(f"<b>{escape(data.label('explore'))}</b> (explore) answers {100 * cfg['explore_share']:.0f}% of every kind with random draws that feed the models"
                     + (f": {e.score.iloc[0]:+.1f} over {int(e.requests.iloc[0]):,} requests, low by design." if len(e) else "."))
    ui.html("".join(f'<p class="line">{n}</p>' for n in notes))
    try:
        trend(data.history(), cfg)
    except Exception as err:
        st.warning(f"The score history could not be read: {err}")
    if len(df):
        with st.expander(f"Each request of the last 5 minutes, newest first · {len(df):,} requests, {int((df.strategy == '').sum())} not answered yet"):
            df = df.assign(result=["bought" if p else "clicked" if c else "fallback" if s == "fallback" else "" for p, c, s in zip(df.purchased, df.clicked, df.served_by)],
                           shopper=df.new_shopper.map({True: "new", False: "returning"}), kind=df.route.map(data.ROUTES))
            df["public name"] = df.model_version
            st.dataframe(df[["time", "kind", "page", "shopper", "device", "region", "views", "strategy", "public name", "latency_ms", "result"]].head(200), hide_index=True, height=420,
                         column_config={"latency_ms": st.column_config.NumberColumn("latency ms", format="%.0f")})


# ---------- Strategies ----------
def score_rows(s: dict, b: pd.DataFrame, champion: str, seen: dict | None) -> str:
    """One row per kind of request: running cards show traffic, score and the gap to the champion; tested cards requests and score."""
    mine = b[b.arm == s["name"]]
    serves = ["all"] if s["name"] == "explore" else s["routes"]
    rows = ""
    for route, kind in data.KINDS.items():
        r = mine[mine.route == route]
        if r.empty and not (seen is not None and route in serves):
            continue
        cells = f"<td>{kind}</td>"
        if seen is not None:
            share = seen.get(route, {}).get(s["name"]) if route in serves else None
            cells += f'<td>{ui.mini(share) if share is not None else ""}</td>'
        if r.empty:
            rows += f'<tr>{cells}<td colspan="2"><small>no reading yet</small></td></tr>'
            continue
        r = r.iloc[0]
        if seen is None:
            cells += f"<td>{int(r.requests):,}{few(r.requests)}</td>"
        cells += f'<td class="sc" title="{r.conversion:.2f}% conversion over {int(r.requests):,} requests">{r.score:+.1f}{few(r.requests) if seen is not None else ""}</td>'
        if seen is not None:
            champ = b[(b.arm == champion) & (b.route == route)]
            cells += "<td><small>champion</small></td>" if s["name"] == champion else "<td><small>not compared</small></td>" if route == "all" else f"<td>{ui.signed(r.score - champ.score.iloc[0])}</td>" if len(champ) else "<td><small>no champion here</small></td>"
        rows += f"<tr>{cells}</tr>"
    if not rows:
        return ""
    head = "<th>kind of request</th><th>traffic</th><th>score, 1 h</th><th>vs champion</th>" if seen is not None else "<th>kind of request</th><th>requests</th><th>score, whole run</th>"
    return f'<table class="rt"><tr>{head}</tr>{rows}</table>'


def strategy_card(s: dict, hour: pd.DataFrame, run: pd.DataFrame, share: dict, seen: dict, champion: str) -> None:
    with st.container(border=True, key=f"card_s_{s['name']}"):
        body = (f'<div class="ch"><span class="nm">{escape(s["public"])}</span>{ui.tag(s["tag"])}</div>'
                f'<div class="sub">internal name {escape(s["name"])}</div>'
                f'<p class="desc">{escape(data.brief(s["summary"]))}</p>')
        if s["group"] == "testing":
            body += ui.share_bar(share.get(s["name"], 0.0), "Share of all live traffic, last 5 min") + score_rows(s, hour, champion, seen)
        elif s["group"] == "tested":
            body += score_rows(s, run, champion, None)
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


@st.fragment(run_every=60)
@guarded
def strategies() -> None:
    cfg, reg = data.arms(), data.registry()
    title("Strategies", f"updated {data.stamp()} · refreshes every 60 s")
    hour, df = read_board(60), read_live()
    try:
        run = data.whole_run()
    except Exception:
        run = data._per_route([])
    share, seen = data.shares(df), data.observed(df)
    items = data.strategies(cfg, reg)
    rank = lambda s: (s["name"] != cfg["champion"], s["name"] == "explore", -share.get(s["name"], 0))
    cards = {g: [("s", s) for s in sorted((s for s in items if s["group"] == g), key=rank)] for g in data.GROUPS}
    cards["next"] += [("i", (i, idea)) for i, idea in enumerate(reg["backlog"])]
    columns(cards, lambda c: strategy_card(c[1], hour, run, share, seen, cfg["champion"]) if c[0] == "s" else idea_card(*c[1]), shown=5, noun="strategies")
    st.caption("Each strategy goes by its public name, the one other teams see on the leaderboard. Score: 0 is the organisers' baseline, 100 the hidden model's own picks. "
               "A score is read on one kind of request; \"vs champion\" compares with the champion on the same kind over the same hour. "
               "Tested strategies show their whole run; rows marked \"before the split\" date from when one label covered every kind of request.")


# ---------- hypothesis cards ----------
def nice(slug: str) -> str:
    return slug.replace("-", " ")


def hypothesis_card(h: dict) -> None:
    with st.container(border=True, key=f"card_h_{h['slug']}"):
        line = (h["verdict"] if h["text"] else h["consequence"] or h["verdict"]) if h["group"] == "tested" else h["claim"]
        users = ", ".join(data.label(n) for n in h["used_by"])
        ui.html(f'<div class="cb"><div class="ch"><span class="nm plain">{escape(nice(h["slug"]))}</span>{ui.tag(h["kind"])}</div>'
                + (f'<div class="sub">used by {escape(users)}</div>' if users else "")
                + (f'<p class="note">{escape(data.brief(line))}</p>' if line else "") + "</div>")
        if st.button("Details", key=f"open_h_{h['slug']}", help=f"Open {h['slug']}"):
            open_detail("hypothesis", h["slug"])


def hypotheses() -> None:
    hyps = data.hypotheses(data.registry(), data.arms())
    st.markdown("### Hypotheses about the simulator")
    columns({g: [h for h in hyps if h["group"] == g] for g in data.GROUPS}, hypothesis_card, shown=4, noun="hypotheses")


# ---------- details ----------
def hypothesis_body(h: dict, with_sql: bool = True) -> None:
    for name in ("claim", "verdict", "evidence", "consequence", "test"):
        if h[name]:
            st.markdown(f"**{name.capitalize()}.** {h[name]}")
    if not (h["claim"] or h["verdict"] or h["text"]):
        st.caption("Nothing written yet: it is only named by a strategy or a backlog idea.")
    if h["used_by"]:
        st.markdown("**Used by.** " + ", ".join(f"{data.label(n)} ({n})" for n in h["used_by"]))
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


def score_table(mine: pd.DataFrame, b: pd.DataFrame, name: str, champion: str) -> None:
    champ = b[b.arm == champion].set_index("route").score
    table = pd.DataFrame({"kind of request": mine.route.map(data.KINDS), "public name": mine.labels, "requests": mine.requests,
                          "conversion %": mine.conversion, "score": mine.score,
                          "champion, same requests": mine.route.map(champ) if name != champion else float("nan")})
    table["difference"] = table.score - table["champion, same requests"]
    number = lambda f: st.column_config.NumberColumn(format=f)
    st.dataframe(table.dropna(axis=1, how="all"), hide_index=True, column_config={"conversion %": number("%.2f%%"), "score": number("%+.1f"),
                 "champion, same requests": number("%+.1f"), "difference": number("%+.1f"), "requests": number("localized")})


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
        minutes = st.session_state.get("window") or 60
        for heading, read in ((f"Last {WINDOWS[minutes]}", lambda: data.board(minutes)), ("Whole run, since 13:26 UTC on 14 Nov", data.whole_run)):
            if heading.startswith("Last") and s["group"] != "testing":
                continue
            try:
                b = read()
            except Exception as e:
                st.warning(f"The per-model leaderboard did not answer: {e}")
                continue
            mine = b[b.arm == name]
            st.markdown(f"**{heading}**")
            if mine.empty:
                st.caption("No leaderboard reading (it lists a model from 100 requests).")
            else:
                score_table(mine, b, name, cfg["champion"])
        st.caption("Rows are different kinds of request: compare a row only with the champion's score on the same kind.")
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
    name = f"Strategy · {data.label(key)}" if kind == "strategy" else f"Hypothesis · {nice(key)}"
    st.dialog(name, width="large")(strategy_detail if kind == "strategy" else hypothesis_detail)(key)
