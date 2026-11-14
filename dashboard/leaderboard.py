"""The Leaderboard tab: our models per kind of request, and every team, from the per-model leaderboard.

Score = 100 × (conversion − baseline) / 2.95, conversions in percent points; ± is one standard error of a proportion.
"""
import math

import altair as alt
import pandas as pd
import streamlit as st

import board
import data
import ui
from q2q import evaluate, rt, strategy

WINDOWS = {30: "30 min", 60: "1 h", 180: "3 h"}
KIND_ORDER = list(data.ROUTES.values())


def score(conv: float, base: float) -> float:
    return 100 * (conv - base) / evaluate.ORACLE_GAP


def se(conv: float, n: float) -> tuple[float, float]:
    """(± conversion in points, ± score) for a conversion in percent over n requests."""
    p = conv / 100
    s = 100 * math.sqrt(max(p * (1 - p), 0) / n) if n else float("nan")
    return s, 100 * s / evaluate.ORACLE_GAP


def ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def style(chart):
    return (chart.configure_axis(gridColor="#222C42", domainColor=ui.BORDER, labelColor=ui.MUTED, titleColor=ui.MUTED)
            .configure_view(strokeWidth=0).configure_legend(labelColor=ui.TEXT, titleColor=ui.MUTED).configure_title(color=ui.TEXT, anchor="start"))


def rule(x: float, colour: str, text: str):
    d = pd.DataFrame({"x": [x], "t": [text]})
    line = alt.Chart(d).mark_rule(color=colour, strokeDash=[4, 3], strokeWidth=1.5).encode(x="x:Q", tooltip=[alt.Tooltip("t:N", title="")])
    label = alt.Chart(d).mark_text(color=colour, align="left", dx=4, baseline="top", y=2, fontSize=11).encode(x="x:Q", text="t:N")
    return line + label


def ours(s: dict) -> None:
    ui.html('<p class="line">Which of our strategies is best on each kind of request.</p>')
    base, ref = s["baseline"]["conversion"], s["reference"]["conversion"]
    us = next((t for t in s["teams"] if t["team_id"] == rt.TEAM), None)
    if not us or not us.get("versions"):
        st.info("Our team has no reading in this window.")
        return
    total = sum(v["requests"] for v in us["versions"]) or 1
    rows = []
    for v in us["versions"]:
        mv, n, c = v["model_version"], v["requests"], v["conversion"]
        sc, ss = se(c, n)
        rows.append({"public name": mv, "our name": strategy.decode(mv), "kind": data.ROUTES[strategy.route_of(mv) or "main"],
                     "requests": n, "conversion %": c, "± conv": sc, "score": score(c, base), "± score": ss, "share %": 100 * n / total})
    df = pd.DataFrame(rows)
    df = df[df.requests >= 100].copy()
    if df.empty:
        st.info("None of our models has 100 requests in this window yet.")
        return
    df["kind_rank"] = df.kind.map(KIND_ORDER.index)
    df = df.sort_values(["kind_rank", "score"], ascending=[True, False])
    df["label"] = df["public name"] + " · " + df["our name"]
    df["lo"], df["hi"] = df.score - df["± score"], df.score + df["± score"]
    kinds = [k for k in KIND_ORDER if k in set(df.kind)]
    enc_y = alt.Y("label:N", sort=list(df.label), title=None, axis=alt.Axis(labelLimit=260))
    tip = [alt.Tooltip("label:N", title="model"), alt.Tooltip("kind:N"), alt.Tooltip("score:Q", format="+.1f"), alt.Tooltip("± score:Q", format=".1f"),
           alt.Tooltip("conversion %:Q", format=".2f"), alt.Tooltip("requests:Q", format=",")]
    bars = alt.Chart(df).mark_bar(cornerRadiusEnd=3, height={"band": 0.7}).encode(
        y=enc_y, x=alt.X("score:Q", title="Score"),
        color=alt.Color("kind:N", sort=kinds, scale=alt.Scale(domain=KIND_ORDER, range=ui.SERIES[:3]), legend=alt.Legend(orient="top", title="Kind of request")),
        tooltip=tip)
    err = alt.Chart(df).mark_rule(color=ui.TEXT, strokeWidth=1.5).encode(y=enc_y, x="lo:Q", x2="hi:Q", tooltip=tip)
    chart = bars + err + rule(0, ui.MUTED, "baseline") + rule(score(ref, base), ui.YELLOW, f"reference {score(ref, base):+.0f}")
    st.altair_chart(style(chart.properties(height=max(26 * len(df) + 40, 160))), width="stretch")
    number = lambda f: st.column_config.NumberColumn(format=f)
    st.dataframe(df[["public name", "our name", "kind", "requests", "conversion %", "± conv", "score", "± score", "share %"]], hide_index=True, width="stretch",
                 column_config={"requests": number("localized"), "conversion %": number("%.2f%%"), "± conv": number("%.2f"), "score": number("%+.1f"),
                                "± score": number("%.1f"), "share %": number("%.0f%%")})
    st.caption("Bars are the score, lines one standard error either side. Compare models only inside one kind of request: each kind is a different kind of shopper. "
               "Models with under 100 requests are left out; share is of all our requests in the window.")


def teams(s: dict) -> None:
    ui.html('<p class="line">Where we stand, and how good the best single model of each team is.</p>')
    base, ref = s["baseline"]["conversion"], s["reference"]["conversion"]
    t = pd.DataFrame([{"team": x["team_id"], "requests": x["requests"], "conversion %": x["conversion"]} for x in s["teams"]])
    t["score"] = score(t["conversion %"], base)
    t = t.sort_values("score", ascending=False).reset_index(drop=True)
    t["rank"] = t.index + 1
    t["who"] = ["us" if x == rt.TEAM else "other teams" for x in t.team]
    mine = t[t.team == rt.TEAM]
    head = f"We are {ordinal(int(mine['rank'].iloc[0]))} of {len(t)}" if len(mine) else f"We are not on the board ({len(t)} teams)"
    bars = alt.Chart(t).mark_bar(cornerRadiusEnd=3, height={"band": 0.75}).encode(
        y=alt.Y("team:N", sort=list(t.team), title=None), x=alt.X("score:Q", title="Team score"),
        color=alt.Color("who:N", scale=alt.Scale(domain=["us", "other teams"], range=[ui.BLUE, "#3A4766"]), legend=alt.Legend(orient="top", title=None)),
        tooltip=[alt.Tooltip("rank:Q"), alt.Tooltip("team:N"), alt.Tooltip("score:Q", format="+.1f"), alt.Tooltip("conversion %:Q", format=".2f"), alt.Tooltip("requests:Q", format=",")])
    chart = bars + rule(0, ui.MUTED, "baseline") + rule(score(ref, base), ui.YELLOW, f"reference {score(ref, base):+.0f}")
    st.altair_chart(style(chart.properties(height=16 * len(t) + 50, title=head)), width="stretch")

    st.markdown("### Best model of each team")
    overall = t.set_index("team").score
    best = []
    for x in s["teams"]:
        vs = x.get("versions") or []
        pool = [v for v in vs if v["requests"] >= 500] or [v for v in vs if v["requests"] >= 300]
        if not pool:
            continue
        v = max(pool, key=lambda v: v["conversion"])
        best.append({"team": x["team_id"], "model_version": v["model_version"], "requests": v["requests"], "conversion %": v["conversion"],
                     "score": score(v["conversion"], base), "± score": se(v["conversion"], v["requests"])[1], "team score": overall[x["team_id"]]})
    if not best:
        st.info("No team has a model with 300 requests in this window.")
        return
    b = pd.DataFrame(best).sort_values("score", ascending=False).reset_index(drop=True)
    b.insert(0, "rank", b.index + 1)
    number = lambda f: st.column_config.NumberColumn(format=f)
    mark = lambda row: [f"background-color: rgba(86,180,233,.22); font-weight: 650" if row.team == rt.TEAM else ""] * len(row)
    st.dataframe(b.style.apply(mark, axis=1), hide_index=True, width="stretch",
                 column_config={"requests": number("localized"), "conversion %": number("%.2f%%"), "score": number("%+.1f"),
                                "± score": number("%.1f"), "team score": number("%+.1f")})
    st.caption("A team's best model is its highest conversion among models with at least 500 requests in the window (300 if it has none). "
               "Other teams' models may answer only one kind of request, so a single model's number is not comparable with a whole-team number.")


@st.fragment(run_every=60)
@board.guarded
def leaderboard() -> None:
    top = st.columns([3, 3, 4], vertical_alignment="center")
    top[0].markdown("### Leaderboard, per model")
    minutes = top[1].radio("Window", list(WINDOWS), index=1, format_func=lambda m: "last " + WINDOWS[m], horizontal=True, key="lb_window", label_visibility="collapsed")
    s, error = data.state(minutes)
    reading = f"window to {evaluate.iso(s['window'][1])[11:16]} UTC" if s and s.get("window") else "no reading"
    top[2].markdown(f'<div class="stamp" style="text-align:right">updated {data.stamp()} · {reading} · refreshes every 60 s</div>', unsafe_allow_html=True)
    st.caption("Per model, one hour is the shortest window worth reading: at 1,000 requests the score is known to about ±14 points.")
    if error:
        st.warning("The leaderboard did not answer" + (", so the previous reading is shown." if s else f": {error}"))
    if not s:
        return
    view = st.segmented_control("View", ["Our models", "All teams"], default="Our models", key="lb_view", label_visibility="collapsed") or "Our models"
    (ours if view == "Our models" else teams)(s)
