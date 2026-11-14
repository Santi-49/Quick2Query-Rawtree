# /// script
# requires-python = ">=3.10"
# dependencies = ["requests"]
# ///
"""Track the "Changes during the event" list on the datathon page.

    uv run scripts/keep_running.py scripts/site_changes.py

Every 5 minutes: fetch the page, append entries not seen before to docs/EVENT_CHANGES.md and print them.
"""
import html
import re
import time
from pathlib import Path

import requests

OUT = Path(__file__).resolve().parent.parent / "docs" / "EVENT_CHANGES.md"
NL = chr(10)
HEAD = "# Changes announced by the organisers" + NL + NL + "From the datathon page, oldest first. Times are Barcelona time." + NL
ITEM = re.compile(r'<li><time datetime="([^"]+)">.*?</time><div><h3>(.*?)</h3><p>(.*?)</p>', re.S)


def clean(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


while True:
    try:
        page = requests.get("https://datathon.rawtree.dev/", timeout=20).text
        known = OUT.read_text(encoding="utf-8") if OUT.exists() else HEAD
        new = [(when, clean(title), clean(text)) for when, title, text in reversed(ITEM.findall(page)) if when not in known]
        for when, title, text in new:
            known += f"{NL}- **{when[:16].replace('T', ' ')} · {title}.** {text}{NL}"
            print(f"NEW {when} {title}", flush=True)
        if new:
            OUT.write_text(known, encoding="utf-8", newline=NL)
    except Exception as e:
        print(f"error: {e}", flush=True)
    time.sleep(300)
