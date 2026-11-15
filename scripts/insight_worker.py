"""Insight workers: take the oldest open question, claim it, answer it with headless Claude Code over the RawTree MCP.

    uv run scripts/insight_worker.py --workers 3 --runs 2 [--name w]

Each answer is an insight row in team_01.scratch; its follow-ups become new questions. Safe on many machines at once:
a question goes to the earliest claim. Claude binary: $CLAUDE_BIN, else the newest VS Code extension build.
"""
import argparse
import glob
import json
import os
import subprocess
import threading
import time
from pathlib import Path

from q2q import memory

ROOT = Path(__file__).resolve().parents[1]
TIMEOUT = 240
TOOLS = "mcp__rawtree__run-query,mcp__rawtree__describe-table,mcp__rawtree__list-tables"
PROMPT = """You are an insight analyst for an e-commerce shopper simulator whose data lives in RawTree.
Tables: shop.requests, shop.events, shop.history_events, shop.catalog, shop.catalog_updates, team_01.feedback.
Every column is Dynamic, so cast before use: x::String, ts::DateTime64(3), shown::Array(String), is_new_user::Bool.
Use describe-table if you need a table's columns. The time now is {now} UTC.

Question: {question}

Answer it ONLY by running read-only aggregate SQL through the RawTree MCP tools (database team_01).
At most 4 queries. Every query has a LIMIT and ends with SETTINGS max_execution_time=20. Never insert or modify anything.
End your reply with ONE line of JSON and nothing after it:
{{"sql": "<main query>", "finding": "<2 sentences with numbers>", "verdict": "supported|rejected|open", "next": ["<follow-up question>", "... at most 2"]}}"""


def claude_bin() -> str:
    found = sorted(glob.glob(os.path.expanduser("~/.vscode/extensions/anthropic.claude-code-*/resources/native-binary/claude.exe")),
                   key=os.path.getmtime)
    return os.environ.get("CLAUDE_BIN") or found[-1]


def ask_claude(question: str) -> tuple[dict, list[str], int]:
    """Run one headless session; return the final JSON, the tool names used and the number of RawTree MCP calls."""
    cmd = [claude_bin(), "-p", PROMPT.format(now=memory.now()[:16], question=question),
           "--mcp-config", str(ROOT / ".mcp.json"), "--strict-mcp-config", "--output-format", "stream-json", "--verbose",
           "--allowedTools", TOOLS, "--disallowedTools", "Bash,Edit,Write,WebFetch,WebSearch",
           "--max-turns", "12", "--no-session-persistence"]
    out = subprocess.run(cmd, cwd=ROOT, env=dict(os.environ), stdin=subprocess.DEVNULL, capture_output=True,
                         timeout=TIMEOUT, encoding="utf-8", errors="replace").stdout  # rt already loaded .env into os.environ
    tools, result = [], ""
    for line in out.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") == "assistant":
            tools += [c["name"] for c in event["message"]["content"] if c.get("type") == "tool_use"]
        elif event.get("type") == "result":
            result = event.get("result") or ""
    for line in reversed(result.strip().splitlines()):
        line = line.strip().strip("`")
        if line.startswith("{") and '"finding"' in line:
            return json.loads(line), tools, sum(t.startswith("mcp__rawtree__") for t in tools)
    raise ValueError(f"no JSON line in the result: {result[-300:]!r}")


def work(agent: str, runs: int) -> None:
    for _ in range(runs):
        q = next((q for q in memory.open_questions() if memory.claim(q["id"], agent)), None)
        if q is None:
            print(f"{agent}: no open question")
            return
        start = time.time()
        try:
            answer, tools, mcp_calls = ask_claude(q["text"])
            verdict = answer.get("verdict") if answer.get("verdict") in ("supported", "rejected", "open") else "open"
            memory.record(q["id"], agent, q["text"], answer.get("sql", ""), answer.get("finding", ""), verdict,
                          next=list(answer.get("next") or [])[:2], tools_used=tools, mcp_calls=mcp_calls,
                          duration_s=time.time() - start)
            print(f"{agent} {q['id']} {verdict} mcp_calls={mcp_calls} {time.time() - start:.0f}s")
        except Exception as e:  # the claim expires after 15 min and the question reopens
            print(f"{agent} {q['id']} failed: {type(e).__name__}: {str(e)[:200]}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--runs", type=int, default=1)
    p.add_argument("--name", default="w")
    a = p.parse_args()
    threads = [threading.Thread(target=work, args=(f"{a.name}{i + 1}", a.runs)) for i in range(a.workers)]
    for i, t in enumerate(threads):
        t.start()
        time.sleep(3)  # stagger, so the workers rarely race for the same question
    for t in threads:
        t.join()


if __name__ == "__main__":
    main()
