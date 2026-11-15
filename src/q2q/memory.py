"""Shared memory of the insight loop: question, claim and insight rows in team_01.scratch.

Append-only; the latest row per id wins. Any agent or human on any machine sees the same state.
    ask("Do home shoppers ...?")           -> question id
    claim(qid, "w1")                         -> True when this agent owns the question
    record(qid, "w1", question, sql, finding, verdict, next=[...])
    open_questions(), insights()
"""
import time
import uuid
from datetime import datetime, timezone

from q2q import rt

CLAIM_TTL = 15 * 60
LIGHT = "SETTINGS max_execution_time=20"


def now() -> str:
    """UTC, in the 'YYYY-MM-DD HH:MM:SS.fff' form the other scratch rows use (RawTree reads it as DateTime64)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def _secs(ts) -> float:
    """Seconds since epoch from an ISO string or RawTree's 'YYYY-MM-DD HH:MM:SS.fff' rendering."""
    s = str(ts).replace("T", " ").rstrip("Z")[:23]
    return datetime.strptime(s if "." in s else s + ".000", "%Y-%m-%d %H:%M:%S.%f").replace(tzinfo=timezone.utc).timestamp()


def ask(text: str, origin: str = "human", parent: str = "", ts: str = "") -> str:
    qid = "q-" + uuid.uuid4().hex[:10]
    rt.insert("scratch", [{"kind": "question", "id": qid, "ts": ts or now(), "text": text, "origin": origin, "parent": parent}])
    return qid


def claim(qid: str, agent: str) -> bool:
    """Insert a claim, re-read all live claims on the question; the earliest (then lowest agent name) wins."""
    if _done(qid):
        return False
    rt.insert("scratch", [{"kind": "claim", "id": qid, "agent": agent, "ts": now()}])
    time.sleep(2.0)  # let concurrent claims land before we read (inserts show up within about a second)
    rows = rt.query(f"""SELECT agent::String agent, toString(ts) ts FROM {{TEAM}}.scratch
        WHERE kind::String = 'claim' AND id::String = '{qid}' LIMIT 100 {LIGHT}""")
    live = sorted((_secs(r["ts"]), r["agent"]) for r in rows if time.time() - _secs(r["ts"]) < CLAIM_TTL)
    return bool(live) and live[0][1] == agent and not _done(qid)


def _done(qid: str) -> bool:
    return bool(rt.query(f"SELECT 1 FROM {{TEAM}}.scratch WHERE kind::String = 'insight' AND id::String = '{qid}' LIMIT 1 {LIGHT}"))


def record(qid: str, agent: str, question: str, sql: str, finding: str, verdict: str, next: list[str] = (),
           source: str = "live", tools_used: list[str] = (), mcp_calls: int = 0, duration_s: float = 0, ts: str = "") -> None:
    """Store an insight and enqueue each follow-up as a new question."""
    rt.insert("scratch", [{"kind": "insight", "id": qid, "ts": ts or now(), "agent": agent, "source": source,
                           "question": question, "sql": sql, "finding": finding, "verdict": verdict, "next": list(next),
                           "tools_used": list(tools_used), "mcp_calls": int(mcp_calls), "duration_s": round(duration_s, 1)}])
    for text in next:
        ask(text, origin=f"agent:{agent}", parent=qid)


def open_questions(limit: int = 200) -> list[dict]:
    """Questions with no insight and no live claim, oldest first."""
    rows = rt.query(f"""SELECT kind::String kind, id::String id, toString(ts) ts, text::String text,
            origin::String origin, parent::String parent
        FROM {{TEAM}}.scratch WHERE kind::String IN ('question', 'claim', 'insight') LIMIT 20000 {LIGHT}""")
    done = {r["id"] for r in rows if r["kind"] == "insight"}
    held = {r["id"] for r in rows if r["kind"] == "claim" and time.time() - _secs(r["ts"]) < CLAIM_TTL}
    qs = {}
    for r in sorted((r for r in rows if r["kind"] == "question"), key=lambda r: _secs(r["ts"])):
        qs.setdefault(r["id"], r)["text"] = r["text"]  # latest text wins, first ts keeps the queue order
    out = [q for q in qs.values() if q["id"] not in done and q["id"] not in held]
    return sorted(out, key=lambda q: _secs(q["ts"]))[:limit]


def insights(limit: int = 50) -> list[dict]:
    """Most recent insights, newest first."""
    return rt.query(f"""SELECT id::String id, toString(ts) ts, agent::String agent, source::String source,
            question::String question, finding::String finding, verdict::String verdict, mcp_calls::Int64 mcp_calls
        FROM {{TEAM}}.scratch WHERE kind::String = 'insight' ORDER BY ts::DateTime64(3) DESC LIMIT {int(limit)} {LIGHT}""")
