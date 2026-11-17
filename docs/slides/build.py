"""Builds docs/slides/quick2query-rawtree.pptx on the four pages of the Canva template.
Run: uv run --with python-pptx --with pillow python docs/slides/build.py"""
from pathlib import Path

from PIL import Image, ImageDraw
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

HERE = Path(__file__).parent
A = HERE / "assets"
ROOT = HERE.parents[1]
SANS, MONO = "Arial", "Consolas"
THEME = {
    "light": dict(ink="0A1C47", body="2F3540", muted="5B6472", accent="3557A8", panel="E6EAEF"),
    "dark": dict(ink="FFFFFF", body="E3E3E3", muted="B4B4B4", accent="9DB8E8", panel="363636"),
}

# The template pages carry their own page number; paint it out so slides can be numbered here.
for n, fill in ((2, (208, 215, 221)), (3, (66, 66, 66))):
    im = Image.open(A / f"tpl-{n}.png").convert("RGB")
    ImageDraw.Draw(im).rectangle([1900, 1030, 2000, 1125], fill=fill)
    im.save(A / f"bg-{n}.png")
BG = {"light": A / "bg-2.png", "dark": A / "bg-3.png", "cover": A / "tpl-1.png", "close": A / "tpl-4.png"}

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
L, R = 0.76, 12.58          # the template's left and right margins, in inches
W = R - L


def rgb(h):
    return RGBColor.from_string(h)


def text(s, x, y, w, h, lines, size=18, color="2F3540", bold=False, font=SANS, align=PP_ALIGN.LEFT,
         anchor=MSO_ANCHOR.TOP, space=0):
    """lines: a string, or a list of strings / (string, {overrides}) pairs, one paragraph each."""
    tf = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h)).text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    for i, ln in enumerate([lines] if isinstance(lines, str) else lines):
        t, o = ln if isinstance(ln, tuple) else (ln, {})
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        if i:
            p.space_before = Pt(o.get("space", space))
        r = p.add_run()
        r.text = t
        f = r.font
        f.name, f.size, f.bold = o.get("font", font), Pt(o.get("size", size)), o.get("bold", bold)
        f.color.rgb = rgb(o.get("color", color))
    return tf


def box(s, x, y, w, h, fill):
    b = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    b.shadow.inherit = False
    b.fill.solid()
    b.fill.fore_color.rgb = rgb(fill)
    b.line.fill.background()
    return b


def slide(kind, title=None, n=None):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    s.shapes.add_picture(str(BG[kind]), 0, 0, prs.slide_width, prs.slide_height)
    t = THEME.get(kind)
    if title:
        text(s, L, 1.38, W, 0.8, title, size=34, bold=True, color=t["ink"])
    if n:
        text(s, 12.4, 6.95, 0.6, 0.3, str(n), size=12, color=t["muted"], align=PP_ALIGN.RIGHT)
    return s, t


def row(s, t, y, label, body, h=0.62):
    """A stored row, shown in monospace: what the data actually looks like."""
    box(s, L, y, W, h, t["panel"])
    text(s, L + 0.2, y, 1.5, h, label, size=11, bold=True, color=t["accent"], font=MONO, anchor=MSO_ANCHOR.MIDDLE)
    text(s, L + 1.75, y, W - 1.95, h, body, size=11, color=t["body"], font=MONO, anchor=MSO_ANCHOR.MIDDLE)


def stat(s, t, x, y, w, number, label, size=44):
    text(s, x, y, w, 0.8, number, size=size, bold=True, color=t["ink"])
    text(s, x, y + size / 72 + 0.22, w, 0.7, label, size=14, color=t["muted"])


def card(s, t, x, y, w, h, head, lines, size=15):
    box(s, x, y, w, h, t["panel"])
    text(s, x + 0.25, y + 0.22, w - 0.5, 0.4, head, size=17, bold=True, color=t["ink"])
    text(s, x + 0.25, y + 0.78, w - 0.5, h - 0.9, lines, size=size, color=t["body"], space=7)


# 1 Cover
s, _ = slide("cover")
text(s, 0.62, 3.55, 9, 0.4, "Datathon FME 2026  ·  team_01", size=14, color="5B6472")
text(s, 0.62, 3.95, 11, 0.8, "One developer, 45 agents, one weekend.", size=32, bold=True, color="0A1C47")

# 2 The problem
s, t = slide("light", "A shop that never stops changing", 2)
for i, (num, lab) in enumerate([("0.3 s", "between one shopper and the next"), ("10", "products to recommend to each one"),
                                ("3 s", "to answer, or the answer is lost")]):
    stat(s, t, L, 2.45 + i * 1.32, 4.2, num, lab, size=38)
pw = 7.1
s.shapes.add_picture(str(ROOT / "docs/readme/live.png"), Inches(R - pw), Inches(2.45), Inches(pw), Inches(pw * 9 / 16))
text(s, L, 6.62, W, 0.4, "What sold yesterday stops selling today, and one person cannot watch it all.", size=16, color=t["body"])

# 3 Way of working
s, t = slide("light", "One hypothesis, one agent", 3)
text(s, L, 2.2, W, 0.5, "The orchestrator plans and hands out the work. Each subagent takes one idea from claim to verdict.",
     size=17, color=t["body"])
steps = [("Hypothesis", "one claim, written down"), ("SQL test", "seconds, on the shop's data"),
         ("Strategy", "one short file"), ("Live verdict", "a share of real shoppers")]
bw, gap = 2.55, 0.54
for i, (h, d) in enumerate(steps):
    x = L + i * (bw + gap)
    box(s, x, 3.05, bw, 1.25, t["panel"])
    text(s, x + 0.22, 3.25, bw - 0.4, 0.4, h, size=18, bold=True, color=t["ink"])
    text(s, x + 0.22, 3.72, bw - 0.4, 0.4, d, size=13, color=t["muted"])
    if i < 3:
        text(s, x + bw, 3.05, gap, 1.25, "→", size=22, color=t["accent"], align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
text(s, L, 4.45, W, 0.35, "The verdict writes the next hypothesis.", size=14, color=t["muted"])
for i, (num, lab) in enumerate([("45", "subagents"), ("26", "hypotheses with a verdict"), ("31", "strategies built")]):
    stat(s, t, L + i * 3.1, 5.2, 2.9, num, lab, size=38)
text(s, L + 9.3, 5.3, 2.55, 1.3, ["Analyst agents get the tables,", "never our beliefs."], size=14, color=t["body"])

# 4 The night shift
s, t = slide("dark", "The night shift", 4)
text(s, L, 2.2, W, 0.5, "From 18:50 UTC on Saturday, nobody was at the keyboard.", size=17, color=t["body"])
loop = [("Operator", ["Every 15 minutes it reads each", "model's score, then promotes", "or retires."]),
        ("Night agent", ["Follows the operator's results", "and decides what is worth", "trying next."]),
        ("Subagents", ["Build and test the next", "candidate, and queue it for", "the operator."])]
bw, gap = 3.55, 0.585
for i, (h, d) in enumerate(loop):
    x = L + i * (bw + gap)
    box(s, x, 2.95, bw, 1.95, t["panel"])
    text(s, x + 0.25, 3.15, bw - 0.5, 0.4, h, size=19, bold=True, color=t["ink"])
    text(s, x + 0.25, 3.68, bw - 0.5, 1.1, d, size=14, color=t["body"], space=2)
    if i < 2:
        text(s, x + bw, 2.95, gap, 1.95, "→", size=22, color=t["accent"], align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
text(s, L, 5.0, W, 0.35, "The queue leads back to the operator, and the loop runs again.", size=14, color=t["muted"])
row(s, t, 5.7, "operator",
    '{"champion": "shale", "schedule": ["shale", "shaleB"], "notes": ["retired shaleE from schedule: '
    'not ahead of shale after 150 minutes (z 0.5)"]}', h=0.8)

# 5 Dev and prod
s, t = slide("light", "Two machines", 5)
cw = (W - 0.5) / 2
card(s, t, L, 2.3, cw, 2.35, "Laptop: where the work happens",
     ["Agents, training and offline tests", "A shadow router: computes every answer, writes nothing",
      "Pushes a new model every 20 minutes"])
card(s, t, L + cw + 0.5, 2.3, cw, 2.35, "VM: what the shoppers see",
     ["The live router and the operator", "Restart on their own after a crash",
      "Load new models and traffic splits without stopping"])
text(s, L, 4.95, W, 0.75, ["On Saturday at 14:20 UTC the laptop went to sleep: 44 minutes of fallback answers.",
                           "That evening production moved to the VM. Only one router may answer, and the lock is a row."],
     size=15, color=t["body"], space=5)
row(s, t, 6.0, "lease", "ts, host, pid, sha, champion, schedule      written every 5 s by the live router")

# 6 Agent memory
s, t = slide("light", "A memory every agent can read", 6)
text(s, L, 2.2, W, 0.5, "An agent starts each session knowing nothing of the last one.", size=17, color=t["body"])
card(s, t, L, 2.85, cw, 2.3, "What is kept",
     ["Every hypothesis and its verdict", "Every strategy tried, and how it scored live",
      "Traffic splits and the operator's decisions"])
card(s, t, L + cw + 0.5, 2.85, cw, 2.3, "Why",
     ["No agent repeats a test that was already run", "Each agent builds on the last result",
      "A crash or a new session loses nothing"])
row(s, t, 5.45, "insight",
    '{"agent": "w3", "verdict": "open", "question": "Which categories gained or lost share of purchases today?", '
    '"finding": "Purchases with no catalog category rose from 3.25% to 10.02% ...", "sql": "WITH p AS (SELECT ...", '
    '"next": ["Which product_ids are missing from the catalog?"]}', h=1.05)

# 7 Telemetry
s, t = slide("dark", "Telemetry: record first", 7)
text(s, L, 2.2, W, 0.5, "Rows of any shape, written as they happen, with no schema to agree on.", size=17, color=t["body"])
cw3 = (W - 0.8) / 3
hi = {"bold": True, "color": t["accent"]}
cols = [("Agents", ["Every tool call: tool, model, tokens, errors", ("2,700+ rows", hi), "Where effort and errors go"]),
        ("VM", ["Every traffic change, every random-share answer, a heartbeat every 5 s", ("17,800+ rows", hi),
                "What was live, and when"]),
        ("Leaderboard", ["A copy of the public board at every refresh", ("45,500+ rows", hi),
                         "Our standing over time, in SQL"])]
for i, (h, d) in enumerate(cols):
    card(s, t, L + i * (cw3 + 0.4), 2.85, cw3, 2.2, h, d, size=14)
text(s, L, 5.3, 2.6, 0.4, "Why it paid off", size=15, bold=True, color=t["accent"])
text(s, L, 5.72, W, 1.1,
     ["We asked the agents about their own traces.",
      "They found that 398 of 399 database calls went through the shell, and none was logged as MCP. We fixed the logging."],
     size=16, color=t["ink"], space=4)

# 8 What the weekend left behind
s, t = slide("light", "What the weekend left behind", 8)
nodes = [("Ask", "a question row", 0, 0), ("Test", "SQL on the shop's data", 1, 0),
         ("Serve", "a share of live shoppers", 1, 1), ("Record", "rows of any shape", 0, 1)]
bw, bh, gx, gy, y0 = 2.3, 1.2, 0.75, 0.7, 2.45
for h, d, cx, cy in nodes:
    x, y = L + cx * (bw + gx), y0 + cy * (bh + gy)
    box(s, x, y, bw, bh, t["panel"])
    text(s, x + 0.2, y + 0.2, bw - 0.4, 0.4, h, size=18, bold=True, color=t["ink"])
    text(s, x + 0.2, y + 0.66, bw - 0.4, 0.4, d, size=12, color=t["muted"])
mid = dict(size=22, color=t["accent"], align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
text(s, L + bw, y0, gx, bh, "→", **mid)
text(s, L + bw, y0 + bh + gy, gx, bh, "←", **mid)
text(s, L + bw + gx, y0 + bh, bw, gy, "↓", **mid)
text(s, L, y0 + bh, bw, gy, "↑", **mid)
text(s, L, 6.25, 5.4, 0.6, "Every step reads and writes the same table.", size=14, color=t["muted"])
grid = [("63,000+", "rows"), ("10", "kinds of row"), ("1", "table"),
        ("0", "schemas written"), ("2,500", "agent tool calls"), ("411", "queries run by agents")]
for i, (num, lab) in enumerate(grid):
    stat(s, t, 6.55 + (i % 3) * 2.1, 2.45 + (i // 3) * 1.9, 2.0, num, lab, size=30)

# 9 Results
s, t = slide("light", "Result", 9)
text(s, L, 2.3, 6, 1.5, "10th of 42", size=80, bold=True, color=t["ink"])
text(s, L, 3.85, 6, 0.4, "Final round, 15 November, 09:00 to 11:00 UTC, leaderboard hidden", size=14, color=t["muted"])
for i, (num, lab) in enumerate([("1.99%", "of shoppers bought (baseline 0.75%)"), ("99.99%", "answered on time"),
                                ("21,600", "shoppers answered in the final")]):
    stat(s, t, L + i * 4.0, 4.9, 3.7, num, lab, size=40)
text(s, L, 6.5, W, 0.4, "Best rank during the practice rounds: 8th of 42.", size=14, color=t["muted"])

# 10 Close
slide("close")

out = HERE / "quick2query-rawtree.pptx"
prs.save(out)
print(out)
