"""Write site/stats.json: how the project was built (Claude Code sessions, files) and the state of the insight memory.

    uv run scripts/agent_stats.py

Reads only counts from the transcripts, never their content.
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from q2q import memory, rt

ROOT = Path(__file__).resolve().parents[1]
TRANSCRIPTS = Path.home() / ".claude" / "projects" / "c--Users-romag-Documents-datathon-fme-2026"
TOOL_USE = re.compile(r'"type":"tool_use","id":"([^"]+)","name":"([^"]+)"')


def main() -> None:
    calls = {}
    for f in TRANSCRIPTS.rglob("*.jsonl"):
        calls.update(TOOL_USE.findall(f.read_text(encoding="utf-8", errors="replace")))
    counts = {r["k"]: int(r["n"]) for r in rt.query("""
        SELECT concat(kind::String, ':', source::String) k, count() n FROM {TEAM}.scratch
        WHERE kind::String = 'insight' GROUP BY k LIMIT 10 SETTINGS max_execution_time=20""")}
    mcp = rt.query("""SELECT sum(mcp_calls::Int64) n FROM {TEAM}.scratch
        WHERE kind::String = 'insight' LIMIT 1 SETTINGS max_execution_time=20""")[0]["n"]
    stats = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "developers": 1,
        "sessions": len(list(TRANSCRIPTS.glob("*.jsonl"))),
        "tool_calls": len(calls),
        "subagents": sum(name in ("Agent", "Task") for name in calls.values()),
        "strategy_files": len([p for p in (ROOT / "src/q2q/strategies").glob("*.py") if p.name != "__init__.py"]),
        "hypothesis_files": len(list((ROOT / "docs/hypotheses").glob("H-*.md"))),
        "sql_files": len(list((ROOT / "sql").rglob("*.sql"))),
        "journal_entries": sum(l.startswith("- ") for l in (ROOT / "docs/JOURNAL.md").read_text(encoding="utf-8").splitlines()),
        "insight_rows_live": counts.get("insight:live", 0),
        "insight_rows_backfill": counts.get("insight:backfill", 0),
        "questions_open": len(memory.open_questions(1000)),
        "mcp_calls_total": int(mcp or 0),
    }
    (ROOT / "site").mkdir(exist_ok=True)
    (ROOT / "site" / "stats.json").write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
