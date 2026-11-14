"""Append one item to updates.jsonl, the project's news feed (the dashboard's Updates tab).

    uv run scripts/note.py <kind> "<title>" "<text>" [--strategy name]

Kinds: building, live, result, champion, finding, dropped, ops. From Python: note.add(kind, title, text, strategy="").
"""
import argparse
import json
import os
import time
from pathlib import Path

FILE = Path(__file__).resolve().parents[1] / "updates.jsonl"
KINDS = ("building", "live", "result", "champion", "finding", "dropped", "ops")


def add(kind: str, title: str, text: str, strategy: str = "") -> dict:
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {', '.join(KINDS)}")
    item = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "kind": kind, "title": title, "text": text, "strategy": strategy}
    fd = os.open(FILE, os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_BINARY", 0))
    try:
        os.write(fd, (json.dumps(item, ensure_ascii=False) + "\n").encode("utf-8"))  # one write, so lines of concurrent writers do not mix
    finally:
        os.close(fd)
    return item


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Append one item to updates.jsonl.")
    p.add_argument("kind", choices=KINDS)
    p.add_argument("title")
    p.add_argument("text")
    p.add_argument("--strategy", default="")
    a = p.parse_args()
    print(json.dumps(add(a.kind, a.title, a.text, a.strategy), ensure_ascii=False))
