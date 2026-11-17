"""Live demo site. One thread reads RawTree every 5 s into a cache; viewers only read the cache.

    uv run python site/app.py            # http://127.0.0.1:8787 (PORT=8788 for another)
    SIMULATE=1 uv run python site/app.py # replay the final 09:00-11:00 UTC, 15 Nov; on by default after it, SIMULATE=0 for off
    SHOW_NAMES=1 uv run python site/app.py   # also decode model_version into strategy names
"""
import calendar
import json
import re
import os
import threading
import time
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

from q2q import rt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
LIMIT = " SETTINGS max_execution_time=10"
REQ = "(SELECT request_id::String FROM shop.requests WHERE ts::DateTime64(3) > now64(3) - INTERVAL 3 MINUTE AND ts::DateTime64(3) <= now64(3))"

SQL = {
    "stream": f"""
SELECT r.ts::String AS ts, r.request_id::String AS rid, r.is_new_user::Bool AS new_user,
       length(r.recent_views::Array(JSON)) AS views, s.mv AS mv, s.items AS items,
       f.n AS fb, f.clicked AS clicked, f.purchased AS purchased, f.latency AS latency, f.served_by AS served_by
FROM (SELECT * FROM shop.requests WHERE ts::DateTime64(3) > now64(3) - INTERVAL 3 MINUTE AND ts::DateTime64(3) <= now64(3) ORDER BY ts::DateTime64(3) DESC LIMIT 240) r
LEFT JOIN (SELECT request_id::String AS rid, any(model_version::String) AS mv, any(items::Array(String)) AS items
           FROM {{TEAM}}.submissions WHERE request_id::String IN {REQ} GROUP BY rid) s ON s.rid = r.request_id::String
LEFT JOIN (SELECT request_id::String AS rid, count() AS n, any(clicked::String) AS clicked, any(purchased::String) AS purchased,
                  any(toFloat64OrZero(toString(latency_ms))) AS latency, any(served_by::String) AS served_by
           FROM {{TEAM}}.feedback WHERE ts::DateTime64(3) > now64(3) - INTERVAL 4 MINUTE AND ts::DateTime64(3) <= now64(3) GROUP BY rid) f ON f.rid = r.request_id::String
ORDER BY r.ts::DateTime64(3) DESC""",
    "minutes": """
SELECT toStartOfMinute(ts::DateTime64(3))::String AS m, count() AS n, countIf(clicked::String != '') AS clicks,
       countIf(purchased::String != '') AS buys, round(sum(toFloat64OrZero(toString(revenue_eur))), 2) AS revenue,
       quantile(0.5)(toFloat64OrZero(toString(latency_ms))) AS p50
FROM {TEAM}.feedback WHERE ts::DateTime64(3) > now64(3) - INTERVAL 120 MINUTE AND ts::DateTime64(3) <= now64(3) GROUP BY m ORDER BY m""",
    "slots": """
SELECT indexOf(shown::Array(String), clicked::String) AS slot, count() AS n
FROM {TEAM}.feedback WHERE ts::DateTime64(3) > now64(3) - INTERVAL 60 MINUTE AND ts::DateTime64(3) <= now64(3) AND clicked::String != ''
GROUP BY slot ORDER BY slot""",
    "today": """
SELECT count() AS n, countIf(served_by::String = 'team') AS on_time, countIf(purchased::String != '') AS buys,
       round(sum(toFloat64OrZero(toString(revenue_eur))), 2) AS revenue, uniqExact(model_version::String) AS labels
FROM {TEAM}.feedback WHERE ts::DateTime64(3) >= toStartOfDay(now64(3)) AND ts::DateTime64(3) <= now64(3)""",
    "arms": """
SELECT model_version::String AS mv, count() AS n FROM {TEAM}.feedback
WHERE ts::DateTime64(3) > now64(3) - INTERVAL 15 MINUTE AND ts::DateTime64(3) <= now64(3) AND served_by::String = 'team' GROUP BY mv ORDER BY n DESC""",
    "insights": "SELECT * FROM {TEAM}.scratch WHERE kind::String = 'insight' ORDER BY ts::String DESC LIMIT 15",
    "insight_count": "SELECT count() AS n, sum(toInt64OrZero(toString(mcp_calls))) AS mcp FROM {TEAM}.scratch WHERE kind::String = 'insight'",
    "questions": """
SELECT count() AS open FROM (SELECT DISTINCT id::String AS q FROM {TEAM}.scratch WHERE kind::String = 'question')
WHERE q NOT IN (SELECT id::String FROM {TEAM}.scratch WHERE kind::String = 'insight')""",
    "examples": """
SELECT * FROM {TEAM}.scratch
WHERE kind::String IN ('agent_trace', 'insight', 'question', 'claim', 'arms', 'operator', 'lease', 'explore', 'leaderboard', 'block')
  AND (kind::String != 'leaderboard' OR (team_id::String = '{TEAM}' AND mode::String = 'practice'))
ORDER BY ts::String DESC LIMIT 1 BY kind::String""",
    "lease": "SELECT ts::String AS ts, started::String AS started, dateDiff('second', ts::DateTime64(3), now64(3)) AS age FROM {TEAM}.scratch WHERE kind::String = 'lease' AND ts::DateTime64(3) <= now64(3) ORDER BY ts::String DESC LIMIT 1",
    "traces_who": """
SELECT if(subagent::Bool, 'subagents', 'main sessions') AS who, count() AS calls, uniqExact(agent::String) AS agents,
       countIf(rawtree::Bool) AS rawtree, countIf(is_error::Bool) AS errors, sum(toInt64OrZero(toString(usage.output_tokens))) AS out_tokens
FROM {TEAM}.scratch WHERE kind::String = 'agent_trace' GROUP BY who ORDER BY who""",
    "traces_hour": """
SELECT toStartOfHour(ts::DateTime64(3))::String AS h, count() AS calls, countIf(rawtree::Bool) AS rawtree, countIf(subagent::Bool) AS sub
FROM {TEAM}.scratch WHERE kind::String = 'agent_trace' GROUP BY h ORDER BY h""",
    "lb_rank": """
SELECT toStartOfHour(parseDateTimeBestEffort(t))::String AS h, round(avg(rk), 1) AS rank, count() AS snaps FROM (
  SELECT ts::String AS t, team_id::String AS id,
         rank() OVER (PARTITION BY ts::String ORDER BY toFloat64OrZero(toString(conversion)) DESC) AS rk
  FROM {TEAM}.scratch WHERE kind::String = 'leaderboard' AND mode::String = 'practice' AND team_id::String LIKE 'team_%')
WHERE id = '{TEAM}' GROUP BY h ORDER BY h""",
    "audit": """
SELECT question::String AS q, finding::String AS f, verdict::String AS v, mcp_calls::Int64 AS mcp, ts::String AS ts
FROM {TEAM}.scratch WHERE kind::String = 'insight' AND agent::String LIKE 'self%' ORDER BY ts::String""",
    "verdicts": "SELECT verdict::String AS v, count() AS n FROM {TEAM}.scratch WHERE kind::String = 'insight' GROUP BY v",
    "scratch": "SELECT kind::String AS k, count() AS n, max(ts::String) AS last FROM {TEAM}.scratch GROUP BY k ORDER BY n DESC",
}
EVERY = {"insights": 15, "insight_count": 15, "questions": 15, "scratch": 15, "examples": 30, "lease": 5, "traces_who": 60, "traces_hour": 60, "lb_rank": 300, "verdicts": 30, "audit": 60}   # slower-moving sources, seconds

# Simulation: the live stream ended at 11:00 UTC on 15 Nov 2026. Replay our real final (09:00-11:00 UTC) in a loop,
# shifted to now: every now64(3) above becomes the replay clock, "today" becomes the start of the final.
# On with SIMULATE=1, and by default once the final is over; SIMULATE=0 turns it off.
SIM_START, SIM_LEN, SIM_LEAD = calendar.timegm((2026, 11, 15, 9, 0, 0)), 7200, 300   # the replay starts at 09:05
SIM = os.environ.get("SIMULATE", "1" if time.time() > SIM_START + SIM_LEN else "0") == "1"
ANCHOR = time.time()


def sim_now() -> float:
    return SIM_START + (SIM_LEAD + time.time() - ANCHOR) % SIM_LEN


def stamp(t: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(t)) + f".{int(t * 1000) % 1000:03d}"


def at_now(sql: str) -> str:
    if not SIM:
        return sql
    return (sql.replace("toStartOfDay(now64(3))", f"toDateTime64('{stamp(SIM_START)}', 3)")
               .replace("now64(3)", f"toDateTime64('{stamp(sim_now())}', 3)"))


cache: dict[str, dict] = {}       # name -> {"rows", "at", "error", "ms"}
categories: dict[str, str] = {}
_names = None


def name_of(mv: str) -> str:
    """Strategy behind a label, only with SHOW_NAMES=1. Otherwise the opaque label is the name."""
    global _names
    if os.environ.get("SHOW_NAMES") != "1" or not mv:
        return mv
    if _names is None:
        from q2q import strategy
        _names = strategy.decode
    return _names(mv)


def load_catalog() -> None:
    try:
        for r in rt.query("SELECT product_id::String AS p, category::String AS c FROM shop.catalog" + LIMIT):
            categories[r["p"]] = r["c"]
        for r in rt.query("SELECT product_id::String AS p, any(category::String) AS c FROM shop.catalog_updates "
                          "WHERE change::String = 'new_product' GROUP BY p" + LIMIT):
            categories.setdefault(r["p"], r["c"])
    except Exception as e:
        print("catalog:", type(e).__name__, flush=True)


def refresh() -> None:
    last_catalog = 0.0
    while True:
        start = time.time()
        if start - last_catalog > 300:
            load_catalog()
            last_catalog = start
        for key, sql in SQL.items():
            old = cache.get(key, {})
            if key in EVERY and time.time() - old.get("tried", 0) < EVERY[key]:
                continue
            t = time.time()
            try:
                rows = rt.query(at_now(sql) + LIMIT, timeout=15)
                cache[key] = {"rows": rows, "at": time.time(), "error": "", "ms": round(1000 * (time.time() - t)), "tried": t}
            except Exception as e:   # keep the last good rows, say how old they are
                cache[key] = {**old, "error": str(e)[:160].split("\n")[0], "tried": t}
                cache[key].setdefault("rows", [])
        time.sleep(max(0.5, 5 - (time.time() - start)))


def route(r: dict) -> str:
    if not r["views"]:
        return "home"
    return "new" if r["new_user"] else "returning"


sent_pending: dict[str, float] = {}   # request id -> when it was last sent still waiting


def stream(rows: list[dict]) -> list[dict]:
    """Newest first: at most 4 still waiting for feedback, then answered ones, 25 in all, plus any answered row that was
    sent as waiting in the last 2 minutes: a page may show it, and it needs the outcome."""
    now = time.time()
    pending = [r for r in rows if not r.get("fb")][:4]
    for r in pending:
        sent_pending[r["rid"]] = now
    for rid in [k for k, t in sent_pending.items() if now - t > 120]:
        del sent_pending[rid]
    answered = [r for r in rows if r.get("fb")]
    top = sorted(pending + answered, key=lambda r: r["ts"], reverse=True)[:25]
    keep = {r["rid"] for r in top}
    rows = top + [r for r in answered if r["rid"] in sent_pending and r["rid"] not in keep]
    out = []
    for r in rows:
        items = r.get("items") or []
        out.append({"ts": r["ts"][11:19], "id": r["rid"][2:8], "rid": r["rid"], "route": route(r), "label": name_of(r.get("mv") or ""),
                    "items": [{"p": p, "c": categories.get(p, "?"), "clicked": p == r.get("clicked"), "bought": p == r.get("purchased")} for p in items],
                    "feedback": bool(r.get("fb")), "on_time": r.get("served_by") == "team", "latency": r.get("latency") or 0})
    return out


def scratch_text(v) -> str:
    return v if isinstance(v, str) else "" if v is None else json.dumps(v)


_hide = None


def hide_names(text: str) -> str:
    """Strategy names in agent text become their public labels, as in the stream, unless SHOW_NAMES=1."""
    global _hide
    if os.environ.get("SHOW_NAMES") == "1":
        return text
    if _hide is None:
        from q2q import strategy
        names = [f.stem for f in (ROOT / "src/q2q/strategies").glob("*.py") if f.stem not in ("__init__", "baseline", "explore")]
        pattern = re.compile(r"\b(" + "|".join(sorted(names, key=len, reverse=True)) + r")\b")
        _hide = lambda t: pattern.sub(lambda m: strategy.label(m.group(1)), t)
    return _hide(text)


def insights(rows: list[dict]) -> list[dict]:
    keys = ("ts", "agent", "source", "question", "finding", "verdict")
    return [{**{k: hide_names(scratch_text(r.get(k))) for k in keys}, "ts": scratch_text(r.get("ts"))[:16],
             "mcp_calls": int(r.get("mcp_calls") or 0) if str(r.get("mcp_calls") or "0").isdigit() else 0} for r in rows]


def examples(rows: list[dict]) -> dict:
    """The newest row of each kind, internal names replaced by public labels and the host name hidden."""
    out = {}
    for r in rows:
        r = {k: v for k, v in r.items() if v is not None and k != "progress"}
        text = re.sub(r"instance-[0-9-]+", "prod-vm", hide_names(json.dumps(r, default=str)))
        out[r.get("kind", "?")] = json.loads(text)
    return out


def analysis(rows: dict) -> dict:
    """Results computed in RawTree from the rows we saved without a schema."""
    return {"traces": rows["traces_who"], "trace_hours": rows["traces_hour"], "rank": rows["lb_rank"],
            "verdicts": {r["v"]: r["n"] for r in rows["verdicts"]},
            "audit": json.loads(hide_names(json.dumps(rows["audit"])))}


def stats() -> dict:
    s = {}
    try:
        s = json.loads((HERE / "stats.json").read_text(encoding="utf-8"))
    except Exception:
        pass
    s.setdefault("strategy_files", len([f for f in (ROOT / "src/q2q/strategies").glob("*.py") if f.name != "__init__.py"]))
    s.setdefault("hypothesis_files", len(list((ROOT / "docs/hypotheses").glob("H-*.md"))))
    s.setdefault("sql_files", len(list((ROOT / "sql").rglob("*.sql"))))
    s.setdefault("developers", 1)
    return s


def live() -> dict:
    now = time.time()
    rows = {k: cache.get(k, {}).get("rows", []) for k in SQL}
    minutes = rows["minutes"]
    recent = minutes[-16:-1] or minutes          # last 15 complete minutes
    n15 = sum(m["n"] for m in recent)
    count = (rows["insight_count"] or [{}])[0]
    s = stats()
    s.setdefault("insight_rows_live", count.get("n"))
    s.setdefault("mcp_calls_total", count.get("mcp"))
    return {
        "now": time.strftime("%H:%M:%S", time.gmtime(sim_now() if SIM else now)),
        "sim": {"on": SIM, "now": stamp(sim_now()), "start": stamp(SIM_START), "end": stamp(SIM_START + SIM_LEN)} if SIM else {"on": False},
        "sources": {k: {"age_s": round(now - v["at"], 1) if v.get("at") else None, "ms": v.get("ms"), "error": v.get("error", "")}
                    for k, v in cache.items()},
        "stream_age_s": round(now - cache["stream"]["at"], 1) if cache.get("stream", {}).get("at") else None,
        "stream": stream(rows["stream"]),
        "minutes": minutes,
        "slots": {int(r["slot"]): r["n"] for r in rows["slots"] if 1 <= int(r["slot"]) <= 10},
        "today": (rows["today"] or [{}])[0],
        "last15": {"n": n15, "buys": sum(m["buys"] for m in recent), "clicks": sum(m["clicks"] for m in recent),
                   "conversion": round(100 * sum(m["buys"] for m in recent) / n15, 2) if n15 else None,
                   "p50": recent[-1]["p50"] if recent else None},
        "arms": [{"label": name_of(r["mv"]), "n": r["n"]} for r in rows["arms"]],
        "insights": insights(rows["insights"]),
        "questions_open": (rows["questions"] or [{}])[0].get("open"),
        "scratch": [{"kind": r["k"], "n": r["n"], "last": scratch_text(r["last"])[:16]} for r in rows["scratch"]],
        "analysis": analysis(rows),
        "prod": {k: scratch_text(v)[:19] for k, v in (rows["lease"] or [{}])[0].items()},
        "stats": s,
    }


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(HERE), **k)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/api/live":
            body = json.dumps(live(), default=str).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "public, max-age=2, s-maxage=2")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/api/rawtree":
            rows = {k: cache.get(k, {}).get("rows", []) for k in SQL}
            body = json.dumps({"now": time.strftime("%H:%M:%S", time.gmtime()), "examples": examples(rows["examples"]),
                               "counts": {r["k"]: r["n"] for r in rows["scratch"]}, "analysis": analysis(rows)}, default=str).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "public, max-age=10, s-maxage=10")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path in ("/", "/rawtree") or path.startswith("/static/"):
            self.path = {"/": "/index.html", "/rawtree": "/rawtree.html"}.get(path) or path[len("/static"):]
            if self.path.lstrip("/") not in ("index.html", "rawtree.html", "style.css", "app.js", "logo.png"):
                self.send_error(404)
                return
            super().do_GET()
        else:
            self.send_error(404)

    def end_headers(self):
        if not self.path.startswith("/api/"):
            self.send_header("Cache-Control", "public, max-age=60")
        super().end_headers()

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    threading.Thread(target=refresh, daemon=True).start()
    port = int(os.environ.get("PORT", 8787))
    print(f"http://127.0.0.1:{port}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
