"""Load the agents' own traces into RawTree: one row per tool call, kind = 'agent_trace' in team_01.scratch.

    uv run scripts/ingest_traces.py

Reads the Claude Code transcripts of this project (main sessions and subagents) and keeps the structure, never the
content: which agent called which tool, when, with which input fields, the model, the token usage of that turn,
whether the call failed and how long it took. No prompts, outputs, file contents or command text are stored.
Run it again later: only calls not yet in RawTree are inserted.
"""
import json
import os
import re
from pathlib import Path

from q2q import rt

# Claude Code keeps a project's sessions under ~/.claude/projects/<repo path, every other character as "-">
TRANSCRIPTS = Path(os.environ.get("Q2Q_TRANSCRIPTS") or Path.home() / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(Path(__file__).resolve().parents[1])))
RAWTREE_SHELL = re.compile(r"q\.py|rtree|rt\.query|q2q (pull|report)|run_sql|sql/(reports|hypotheses|features)")


def calls(path: Path):
    """Yield one trace row per tool call in a transcript file."""
    sub = path.parent.name == "subagents"
    agent = path.stem.replace("agent-", "")[:8] if sub else "main"
    session = (path.parent.parent.name if sub else path.stem)[:8]
    pending, results, ts = {}, {}, ""
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        ts = (e.get("timestamp") or "")[:23].replace("T", " ") or ts   # some subagent events carry no time
        m = e.get("message")
        if not isinstance(m, dict) or not isinstance(m.get("content"), list):
            continue
        for c in m["content"]:
            if not isinstance(c, dict):
                continue
            if c.get("type") == "tool_use":
                inp = c.get("input") if isinstance(c.get("input"), dict) else {}
                command = str(inp.get("command", ""))
                u = m.get("usage") or {}
                pending[c["id"]] = {
                    "kind": "agent_trace", "id": c["id"], "ts": ts,
                    "session": session, "agent": agent, "subagent": sub, "tool": c.get("name", ""),
                    "input_fields": sorted(inp.keys()),
                    "rawtree": c.get("name", "").startswith("mcp__rawtree__") or bool(RAWTREE_SHELL.search(command)),
                    "via": "mcp" if c.get("name", "").startswith("mcp__") else "shell" if c.get("name") in ("Bash", "PowerShell") else "tool",
                    "model": m.get("model", ""),
                    "usage": {k: u[k] for k in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens") if k in u},
                }
            elif c.get("type") == "tool_result":
                r = e.get("toolUseResult")
                results[c.get("tool_use_id")] = {"is_error": bool(c.get("is_error")),
                                                  "duration_ms": r.get("durationMs") if isinstance(r, dict) else None}
    for cid, row in pending.items():
        row.update({k: v for k, v in results.get(cid, {"is_error": None}).items() if v is not None})
        yield row


def main() -> None:
    done = {r["id"] for r in rt.query("SELECT id::String AS id FROM {TEAM}.scratch WHERE kind::String = 'agent_trace' LIMIT 1000000")}
    rows = {r["id"]: r for f in sorted(TRANSCRIPTS.rglob("*.jsonl")) for r in calls(f) if r["id"] not in done and r["ts"]}
    rows = sorted(rows.values(), key=lambda r: r["ts"])   # a call copied into a resumed session counts once
    for i in range(0, len(rows), 500):
        rt.insert("scratch", rows[i:i + 500], timeout=60)
    print(f"{len(rows)} tool calls inserted, {len(done)} were already in RawTree")


if __name__ == "__main__":
    main()
