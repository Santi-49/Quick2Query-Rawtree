"""Look of the dashboard: colour tokens, the stylesheet and the small HTML pieces the cards are made of.

Colours are the Okabe-Ito colour-blind-safe set. A status is always a word plus a shape; colour only repeats it.
"""
from html import escape

import streamlit as st

BLUE, ORANGE, GREEN, RED, PINK, YELLOW, GREY = "#56B4E9", "#E69F00", "#35C09A", "#F28E5C", "#D9A0C0", "#F0E442", "#9AA7BD"
SERIES = [BLUE, ORANGE, GREEN, PINK, YELLOW, RED, "#8FA8FF"]
TEXT, MUTED, SURFACE, BORDER = "#E6EBF4", "#9AA7BD", "#161E2E", "#2A3650"

# tag name -> (shape class, colour)
TAGS = {"Champion": ("diamond", YELLOW), "Testing now": ("dot", BLUE), "Tested": ("square", GREY), "Queued": ("ring", GREY),
        "Planned": ("ring", GREY), "Idea": ("ring", GREY),
        "now": ("dot", BLUE), "next": ("ring", BLUE), "later": ("ring", GREY), "done": ("square", GREY), "early": ("half", BLUE),
        "confirmed": ("dot", GREEN), "mixed": ("half", ORANGE), "rejected": ("cross", RED), "open": ("ring", BLUE),
        "live": ("dot", GREEN), "history only": ("ring", ORANGE), "reversed live": ("cross", RED), "live views only": ("half", BLUE)}
WORDS = {"now": "Running now", "next": "Up next", "later": "Later", "done": "Done", "early": "Early reading",
         "confirmed": "Confirmed", "mixed": "Partly confirmed", "rejected": "Rejected", "open": "Open",
         "live": "Confirmed live", "history only": "History only", "reversed live": "Reversed live", "live views only": "Live views only"}

CSS = f"""<style>
:root {{--text:{TEXT}; --muted:{MUTED}; --surface:{SURFACE}; --border:{BORDER}; --blue:{BLUE}; --orange:{ORANGE}}}
.block-container {{padding: 3.6rem 2rem 2rem; max-width: 1480px}}
@media (max-width: 640px) {{.block-container {{padding: 3rem 1rem 1.5rem}}}}
h3 {{font-size: 1.02rem !important; font-weight: 650 !important; padding: .9rem 0 .1rem !important; letter-spacing: 0 !important}}
.num, .hd b, .rt td, .kn-size, .share b {{font-variant-numeric: tabular-nums}}

/* header */
.hd {{display: flex; flex-wrap: wrap; gap: 8px 12px; align-items: stretch; margin: 0 0 .4rem}}
.hd > div {{background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 8px 14px; min-width: 150px; flex: 1 1 150px}}
.hd .brand {{flex: 0 0 auto; min-width: 0; background: none; border: none; padding: 8px 8px 8px 0; font-weight: 700; font-size: 1.15rem; align-self: center}}
.hd span {{display: block; font-size: .75rem; color: var(--muted); line-height: 1.3}}
.hd b {{font-size: 1.12rem; font-weight: 650; line-height: 1.5}}
.hd small {{font-size: .8rem; color: var(--muted); font-weight: 400}}
.stamp {{font-size: .76rem; color: var(--muted); font-variant-numeric: tabular-nums}}

/* column titles and cards */
.col {{display: flex; justify-content: space-between; align-items: baseline; border-bottom: 2px solid var(--border); padding: 0 2px 6px; margin-bottom: 2px}}
.col b {{font-size: .82rem; text-transform: uppercase; letter-spacing: .06em}}
.col span {{font-size: .78rem; color: var(--muted)}}
.empty {{color: var(--muted); font-size: .85rem; padding: 10px 2px}}
[class*="st-key-card_"] {{background: var(--surface); border-color: var(--border) !important; border-radius: 10px; padding: 14px 14px 12px !important; gap: .55rem !important}}
.cb {{padding-bottom: 2px}}
[class*="st-key-card_"] [data-testid="stMarkdownContainer"] {{margin-bottom: 0 !important}}
.cb.solo {{padding-bottom: 6px}}
.cb p {{margin-bottom: 0 !important}}
.ch {{display: flex; justify-content: space-between; align-items: center; gap: 8px}}
.nm {{font-size: 1.08rem; font-weight: 650; text-transform: capitalize; overflow-wrap: anywhere}}
.nm.plain {{text-transform: none; font-size: .98rem}}
.sub {{font-size: .76rem; color: var(--muted); margin-top: 1px}}
.desc {{font-size: .86rem !important; line-height: 1.5; margin: 8px 0 0 !important; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden}}
.note {{font-size: .82rem !important; line-height: 1.45; color: var(--muted); margin: 8px 0 2px !important; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden}}
.tag {{display: inline-flex; align-items: center; gap: 6px; white-space: nowrap; font-size: .74rem; font-weight: 600; padding: 2px 9px 2px 8px; border: 1px solid var(--border); border-radius: 999px; background: #1C2538}}
.tag i {{width: 8px; height: 8px; flex: none; background: var(--c); border-radius: 50%}}
.tag i.square {{border-radius: 1px}}
.tag i.diamond {{border-radius: 1px; transform: rotate(45deg)}}
.tag i.ring {{background: none; border: 2px solid var(--c)}}
.tag i.half {{background: linear-gradient(90deg, var(--c) 50%, transparent 50%); border: 1.5px solid var(--c)}}
.tag i.cross {{background: none; border-radius: 0; position: relative}}
.tag i.cross::before, .tag i.cross::after {{content: ""; position: absolute; left: 3px; top: -1px; width: 2px; height: 10px; background: var(--c); transform: rotate(45deg)}}
.tag i.cross::after {{transform: rotate(-45deg)}}

/* traffic share and score rows */
.share {{display: grid; grid-template-columns: 1fr auto; font-size: .78rem; color: var(--muted); margin-top: 10px; row-gap: 4px}}
.share b {{color: var(--text); font-size: .86rem}}
.bar {{grid-column: 1 / -1; height: 4px; background: #26314A; border-radius: 2px; overflow: hidden}}
.bar div {{height: 100%; background: var(--blue); border-radius: 2px}}
.rt {{width: 100%; border-collapse: collapse; margin-top: 10px; font-size: .82rem}}
.rt td, .rt th {{padding: 4px 0; border: none !important; border-top: 1px solid var(--border) !important; text-align: right; background: none !important}}
.rt th {{font-size: .7rem; font-weight: 500; color: var(--muted); border-top: none !important; padding-bottom: 2px}}
.rt td:first-child, .rt th:first-child {{text-align: left; color: var(--muted)}}
.rt td.sc {{font-weight: 650; font-size: .95rem; color: var(--text)}}
.rt td.vs {{color: var(--muted)}}
.rt tr {{border: none !important}}
.rt td b {{color: var(--text); font-weight: 650; text-transform: capitalize}}
.rt td small {{color: var(--muted); font-size: .72rem}}
.rt td .mini {{display: inline-block; width: 44px; height: 4px; background: #26314A; border-radius: 2px; overflow: hidden; vertical-align: middle; margin-right: 6px}}
.rt td .mini i {{display: block; height: 100%; background: var(--blue)}}
.pos {{color: {GREEN} !important}} .neg {{color: {RED} !important}}
.lead {{font-size: .86rem !important; line-height: 1.45; margin: 10px 0 0 !important; padding-top: 8px; border-top: 1px solid var(--border)}}
.lead small {{color: var(--muted)}}
.line {{font-size: .84rem !important; color: var(--muted); margin: 2px 0 0}}
.line b {{color: var(--text); text-transform: capitalize}}

/* plan */
.pl {{display: grid; grid-template-columns: 9.5rem minmax(0, 1fr); gap: 4px 18px; padding: 12px 4px; border-top: 1px solid var(--border)}}
.pl:first-child {{border-top: none}}
.pl.wide {{grid-template-columns: 17rem minmax(0, 1fr)}}
.pl .wh b {{display: block; font-size: .95rem; font-weight: 650; font-variant-numeric: tabular-nums; margin-bottom: 4px}}
.pl p {{font-size: .88rem !important; line-height: 1.5; margin: 0 0 2px !important}}
.pl p.rule {{color: var(--muted); font-size: .82rem !important}}
.lessons {{margin: 0 0 4px; padding-left: 1.1rem}}
.lessons li {{font-size: .86rem; line-height: 1.5; margin-bottom: 4px}}
@media (max-width: 640px) {{.pl, .pl.wide {{grid-template-columns: 1fr}}}}

/* knowledge */
.kn {{display: grid; grid-template-columns: 1.6rem minmax(0, 5fr) minmax(120px, 2fr) 8.5rem; gap: 6px 16px; align-items: center; padding: 12px 4px; border-top: 1px solid var(--border)}}
.kn:first-child {{border-top: none}}
.kn .rk {{color: var(--muted); font-size: .8rem; font-variant-numeric: tabular-nums}}
.kn .fx b {{font-size: .95rem; font-weight: 650}}
.kn .fx p {{font-size: .84rem; line-height: 1.5; color: var(--muted); margin: 2px 0 0}}
.kn .fx small {{font-size: .76rem; color: var(--muted)}}
.kn-size {{font-size: 1.05rem; font-weight: 650}}
.kn-size small {{font-size: .72rem; font-weight: 400; color: var(--muted); margin-left: 6px}}
.kb {{height: 8px; background: #26314A; border-radius: 4px; overflow: hidden; margin-top: 5px}}
.kb div {{height: 100%; border-radius: 4px; background: var(--blue)}}
.kb div.down {{background: repeating-linear-gradient(135deg, var(--orange) 0 4px, #7A5400 4px 8px)}}
@media (max-width: 640px) {{.kn {{grid-template-columns: 1.4rem 1fr}} .kn .mz, .kn .ev {{grid-column: 2}}}}

/* live */
.lv {{padding-bottom: 8px}}
.lv b {{font-size: .98rem; font-weight: 650}}
.lv .who {{display: grid; grid-template-columns: minmax(0, 1fr) auto; font-size: .86rem; margin-top: 10px; row-gap: 4px}}
.lv .who span small {{color: var(--muted)}}

.stButton button {{min-height: 2.5rem; border-color: var(--border); transition: border-color .15s ease-out, background-color .15s ease-out}}
.stButton button:focus-visible {{outline: 2px solid var(--blue); outline-offset: 2px}}
@media (prefers-reduced-motion: reduce) {{* {{transition: none !important; animation: none !important}}}}
</style>"""


def html(text: str) -> None:
    st.markdown(text, unsafe_allow_html=True)


def tag(name: str) -> str:
    shape, colour = TAGS.get(name, ("ring", GREY))
    return f'<span class="tag"><i class="{shape}" style="--c:{colour}"></i>{escape(WORDS.get(name, name))}</span>'


def column_title(title: str, count: int, hint: str) -> None:
    html(f'<div class="col"><b>{escape(title)} · {count}</b><span>{escape(hint)}</span></div>')


def signed(x: float, unit: str = "") -> str:
    """A difference as text with its sign; colour only repeats the sign."""
    return f'<span class="{"pos" if x > 0 else "neg" if x < 0 else ""}">{x:+.1f}{unit}</span>'


def mini(pct: float) -> str:
    return f'<span class="mini" role="img" aria-label="{pct:.0f} percent"><i style="width:{min(pct, 100):.0f}%"></i></span>{pct:.0f}%'


def share_bar(pct: float, text: str = "Live traffic, last 5 min") -> str:
    return (f'<div class="share"><span>{escape(text)}</span><b>{pct:.0f}%</b>'
            f'<div class="bar" role="img" aria-label="{pct:.0f} percent"><div style="width:{min(pct, 100):.1f}%"></div></div></div>')
