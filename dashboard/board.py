"""The Strategies tab: what is running, what is retired with its conclusion, what is queued, the plan and the backlog.

Reads strategies.toml (registry, plan, backlog), arms.toml (what gets traffic) and the per-model leaderboard.
Select a row to open the detail of a strategy; its hypotheses open underneath.
"""
import importlib
import re
import tomllib

import pandas as pd
import streamlit as st

from q2q import evaluate, rt
from q2q.strategy import ROUTES, label

ROOT = rt.ROOT
ROUTE = {"main": "ordinary", "no_views": "no recent views", "new_shopper": "new shopper"}


@st.cache_data(ttl=60, show_spinner=False)
def board(minutes: int) -> pd.DataFrame:
    return pd.DataFrame(evaluate.models(minutes))


def registry() -> dict:
    return tomllib.loads((ROOT / "strategies.toml").read_text(encoding="utf-8"))


def simulator_rows() -> dict[str, dict]:
    """slug -> {status, text} from the two hypothesis tables of docs/SIMULATOR.md."""
    text, out = (ROOT / "docs/SIMULATOR.md").read_text(encoding="utf-8"), {}
    for title in ("Verdicts on the first hypotheses", "New hypotheses"):
        for line in text.split(f"## {title}")[1].split("\n## ")[0].splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if line.startswith("|") and cells[0] not in ("Slug", "") and not set(cells[0]) <= {"-", " "}:
                first = len(cells) == 4
                out[cells[0]] = {"status": re.sub(r"\*", "", cells[1]).split(",")[0] if first else "open",
                                 "claim": cells[1] if not first else "", "evidence": cells[2] if first else "",
                                 "consequence": cells[3] if first else "", "test": cells[2] if not first else ""}
    return out


def hypothesis(slug: str, sim: dict, expanded: bool = False) -> None:
    """One hypothesis, openable wherever it is mentioned."""
    row, doc = sim.get(slug, {}), ROOT / f"docs/hypotheses/H-{slug}.md"
    status = "tested, write-up below" if doc.exists() else row.get("status", "not written yet")
    with st.expander(f"Hypothesis · {slug} · {status}", expanded=expanded):
        for key in ("claim", "evidence", "consequence", "test"):
            if row.get(key):
                st.markdown(f"**{key.capitalize()}:** {row[key]}")
        if doc.exists():
            st.markdown(doc.read_text(encoding="utf-8"))
        elif not row:
            st.caption("No entry yet in docs/SIMULATOR.md or docs/hypotheses/.")
        if (ROOT / f"sql/hypotheses/H-{slug}.sql").exists():
            st.caption("Its queries can be run live in the Hypotheses tab.")


def status_of(name: str, info: dict, cfg: dict) -> str:
    live = set(cfg["schedule"] or [cfg["champion"]]) | {a for arms in cfg["routes"].values() for a in arms} | {"explore"}
    if name in live:
        return "champion" if name == cfg["champion"] else "running"
    return info.get("status") or "queued"


def render(cfg: dict) -> None:
    reg, sim = registry(), simulator_rows()
    names = sorted(f.stem for f in (ROOT / "src/q2q/strategies").glob("*.py") if f.stem != "__init__")
    minutes = st.radio("Leaderboard window", [15, 30, 60, 180], index=2, horizontal=True, format_func=lambda m: f"{m} min" if m < 60 else f"{m // 60} h")
    try:
        b = board(minutes)
    except Exception as e:
        b = pd.DataFrame()
        st.warning(f"Per-model leaderboard unavailable: {e}")
    rows = []
    for name in names:
        info = reg["strategies"].get(name, {})
        mine = b[b.arm == name] if not b.empty else b
        n = int(mine.requests.sum()) if len(mine) else 0
        conv = float((mine.conversion * mine.requests).sum() / n) if n else None
        rows.append({"strategy": name, "public name": label(name), "status": status_of(name, info, cfg), "requests": n, "conversion %": conv,
                     "score": 100 * (conv - mine.baseline.iloc[0]) / evaluate.ORACLE_GAP if n else None,
                     "conclusion": info.get("conclusion", "not in strategies.toml yet")})
    order = {"champion": 0, "running": 1, "queued": 2, "retired": 3}
    table = pd.DataFrame(rows).sort_values("status", key=lambda s: s.map(order)).reset_index(drop=True)
    counts = table.status.value_counts()
    st.markdown(" ".join(f"<span class='tag'>{k}: {counts.get(k, 0)}</span>" for k in order), unsafe_allow_html=True)
    st.caption("The public name is what the leaderboard shows for us, so other teams learn nothing from it; "
               f"a suffix marks the kind of request: {', '.join(f'{s or chr(34) * 2} {r or chr(111) + chr(114) + chr(100) + chr(105) + chr(110) + chr(97) + chr(114) + chr(121)}' for r, s in ROUTES.items())}. "
               "Select a row to open a strategy. Conversion and score come from the per-model leaderboard in the chosen window; "
               "a strategy that only answers one kind of request is not comparable with the others on this line, see its detail.")
    picked = st.dataframe(table, hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row", key="strategy_table",
                          column_config={"conversion %": st.column_config.NumberColumn(format="%.2f%%"), "score": st.column_config.NumberColumn(format="%+.1f"),
                                         "conclusion": st.column_config.TextColumn(width="large")})
    chosen = picked.selection.rows if picked and picked.selection.rows else [0]
    name = table.strategy[chosen[0]]
    info = reg["strategies"].get(name, {})

    st.markdown(f"### {name} · {table.status[chosen[0]]}")
    a, c = st.columns([3, 2])
    a.markdown(info.get("summary") or (importlib.import_module(f"q2q.strategies.{name}").__doc__ or ""))
    a.markdown(f"**Conclusion so far:** {info.get('conclusion', 'none yet')}")
    mine = b[b.arm == name] if not b.empty else b
    if len(mine):
        detail = mine.assign(route=mine.route.map(ROUTE))[["route", "label", "requests", "conversion", "cold_conversion", "score"]]
        c.dataframe(detail, hide_index=True, column_config={"conversion": st.column_config.NumberColumn("conversion %", format="%.2f%%"),
                    "cold_conversion": st.column_config.NumberColumn("cold %", format="%.2f%%"), "score": st.column_config.NumberColumn(format="%+.1f"),
                    "label": st.column_config.TextColumn("public name")})
        c.caption(f"Baseline {mine.baseline.iloc[0]:.2f}%, reference {mine.reference.iloc[0]:.2f}% in the same window. Compare arms on the same kind of request only.")
    else:
        c.info("No requests in this window, or fewer than the 100 the leaderboard lists.")
    with a.expander("Source code"):
        st.code((ROOT / f"src/q2q/strategies/{name}.py").read_text(encoding="utf-8"), language="python")
    for slug in info.get("hypotheses", []):
        hypothesis(slug, sim)

    left, right = st.columns(2)
    left.markdown("### Plan for the next windows")
    left.dataframe(pd.DataFrame(reg.get("plan", [])), hide_index=True, width="stretch",
                   column_config={"what": st.column_config.TextColumn("what runs", width="large"), "decide": st.column_config.TextColumn("decision rule", width="large")})
    left.caption("Windows are 15 minutes or longer, the shortest the leaderboard reads. Arms run at the same time on separate shoppers.")
    right.markdown("### Backlog: not implemented yet")
    backlog = pd.DataFrame(reg.get("backlog", []))
    pick = right.dataframe(backlog, hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row", key="backlog_table",
                           column_config={"why": st.column_config.TextColumn(width="large")})
    if pick and pick.selection.rows and backlog.hypothesis[pick.selection.rows[0]]:
        with right:
            hypothesis(backlog.hypothesis[pick.selection.rows[0]], sim, expanded=True)
    else:
        right.caption("Select an idea to open the hypothesis behind it.")
