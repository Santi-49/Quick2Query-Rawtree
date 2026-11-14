# /// script
# requires-python = ">=3.10"
# dependencies = ["requests"]
# ///
"""Run SQL against RawTree and print the rows as compact JSON lines.

    uv run scripts/q.py "SELECT count() FROM shop.requests"
    uv run scripts/q.py eda/03-carousel.sql            # every statement in the file, in parallel
    uv run scripts/q.py eda/03-carousel.sql slot       # only statements whose title contains "slot"

In a file, statements end with ';' and the comment line above each one is its title.
{TEAM} is replaced by TEAM_ID.
"""
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
for line in (ROOT / ".env").read_text().splitlines():
    key, _, value = line.partition("=")
    if value and not key.startswith("#"):
        os.environ.setdefault(key.strip(), value.strip())
API = os.environ.get("RAWTREE_API_URL", "https://api.rawtree.com")
http = requests.Session()
http.headers["Authorization"] = f"Bearer {os.environ['RAWTREE_API_KEY']}"


def query(sql: str, timeout: int = 180) -> list[dict]:
    r = http.post(f"{API}/v1/query", json={"sql": sql.replace("{TEAM}", os.environ["TEAM_ID"])}, timeout=timeout)
    if not r.ok:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:1200]}")
    return r.json()["data"]


def statements(text: str) -> list[tuple[str, str]]:
    out = []
    for chunk in text.split(";\n"):
        lines = [l for l in chunk.strip().splitlines() if l.strip()]
        body = "\n".join(l for l in lines if not l.lstrip().startswith("--")).strip().rstrip(";")
        titles = [l.lstrip("- ").strip() for l in lines if l.lstrip().startswith("--")]
        if body:
            out.append((titles[-1] if titles else body[:60], body))
    return out


def run(item: tuple[str, str]) -> str:
    title, sql = item
    start = time.time()
    try:
        rows = query(sql)
        body = "\n".join(json.dumps(r, ensure_ascii=False, default=str) for r in rows)
    except Exception as e:
        body = f"ERROR {e}"
    return f"## {title}  ({time.time() - start:.1f}s)\n{body}\n"


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    arg = sys.argv[1]
    if arg.endswith(".sql"):
        todo = statements(Path(arg).read_text(encoding="utf-8"))
        if len(sys.argv) > 2:
            todo = [t for t in todo if sys.argv[2].lower() in t[0].lower()]
    else:
        todo = [("query", arg)]
    with ThreadPoolExecutor(8) as pool:
        for text in pool.map(run, todo):
            print(text)
