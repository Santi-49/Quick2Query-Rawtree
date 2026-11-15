"""Load the hypotheses already answered into the insight memory, and seed open questions.

    uv run scripts/backfill_memory.py

One insight row (source "backfill") per docs/hypotheses/H-*.md. Idempotent: does nothing when backfill rows exist.
"""
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from q2q import memory, rt

ROOT = Path(__file__).resolve().parents[1]
SEEDS = [
    "Today (15 Nov UTC, the final round starts 09:00), what share of shop.requests are home-page requests, and how does it compare with the same hours of 14 Nov?",
    "How many product_ids seen in shop.events today (15 Nov UTC) are missing from shop.catalog, and what share of today's organic purchases do they take?",
    "Do price changes in shop.catalog_updates move a product's organic purchases per view in the hours after the change, and is a price cut different from a raise?",
    "What is our revenue per request (purchases in team_01.feedback times price_eur) by page type, and is the page with the best conversion also the best in revenue?",
    "Do new shoppers today (15 Nov UTC) come from the same device x region mix as new shoppers on 14 Nov?",
    "Which categories gained or lost share of organic purchases in shop.events today (15 Nov UTC) against the same hours of 14 Nov?",
    "What fraction of home-page requests come from shoppers with an organic cart in shop.events in the 24 hours before the request?",
    "Does the purchase rate per slot in team_01.feedback fall with the slot today (15 Nov UTC) the same way as on 14 Nov?",
]


def field(text: str, name: str) -> str:
    """'- **name**: x', '- **Name:** x' or the body of a '## Name' section, flattened."""
    m = re.search(rf"^- \*\*{name}[^*\n]*?:?\*\*:?\s*(.+)$", text, re.I | re.M)
    if m:
        return m.group(1).strip()
    m = re.search(rf"^## [^\n]*\b{name}\b[^\n]*\n(.*?)(?=^## |\Z)", text, re.I | re.M | re.S)
    return " ".join(m.group(1).split()) if m else ""


def verdict(text: str) -> str:
    t = text.lower()
    if re.search(r"reject|refut|contradict", t) and not re.search(r"confirmed for|confirmed, with|confirmed in part", t):
        return "rejected"
    if re.search(r"confirm|answered|support|small edge", t):
        return "supported"
    return "open"


def when(path: Path, status: str, test: str) -> str:
    """The run time named in the status or test line, else the file's first commit."""
    m = re.search(r"(\d{1,2}) Nov[^\d]{0,12}(\d{1,2}):(\d{2})", status) or \
        re.search(r"\brun (\d{1,2}) Nov[^\d]{0,12}(\d{1,2}):(\d{2})", test)
    if m:
        return f"2026-11-{int(m[1]):02d} {int(m[2]):02d}:{m[3]}:00.000"
    iso = subprocess.run(["git", "log", "--diff-filter=A", "--format=%aI", "--", str(path.relative_to(ROOT))],
                         cwd=ROOT, capture_output=True, text=True).stdout.split()
    t = datetime.fromisoformat(iso[-1]) if iso else datetime.now(timezone.utc)
    return t.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.000")


def main() -> None:
    try:
        done = rt.query("SELECT 1 FROM {TEAM}.scratch WHERE kind::String = 'insight' AND source::String = 'backfill' LIMIT 1")
    except RuntimeError as e:  # the column appears with the first row that has it
        if "UNKNOWN_IDENTIFIER" not in str(e):
            raise
        done = []
    if done:
        print("backfill rows exist, nothing to do")
        return
    n = 0
    for path in sorted((ROOT / "docs" / "hypotheses").glob("H-*.md")):
        text = path.read_text(encoding="utf-8")
        status = field(text, "status")
        sql = ROOT / "sql" / "hypotheses" / (path.stem + ".sql")
        memory.record(
            qid=path.stem, agent="main-session", source="backfill", ts=when(path, status, field(text, "test")),
            question=field(text, "claim")[:1500] or text.splitlines()[0].lstrip("# "),
            sql=sql.read_text(encoding="utf-8")[:4000] if sql.exists() else "",
            finding=(field(text, "result") or status)[:1500],
            verdict=verdict((field(text, "verdict") or "") + " " + status))
        n += 1
    for text in SEEDS:
        memory.ask(text, origin="seed")
    print(f"{n} backfill insights, {len(SEEDS)} seed questions")


if __name__ == "__main__":
    main()
