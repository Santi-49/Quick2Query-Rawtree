"""Live demo site. One thread reads RawTree every 5 s into a cache; viewers only read the cache.

    uv run python site/app.py            # http://127.0.0.1:8787
    SHOW_NAMES=1 uv run python site/app.py   # also decode model_version into strategy names
"""
import json
import os
import threading
import time
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

from q2q import rt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
LIMIT = " SETTINGS max_execution_time=10"
REQ = "(SELECT request_id::String FROM shop.requests WHERE ts::DateTime64(3) > now64(3) - INTERVAL 3 MINUTE)"

SQL = {
    "stream": f"""
SELECT r.ts::String AS ts, r.request_id::String AS rid, r.is_new_user::Bool AS new_user,
       length(r.recent_views::Array(JSON)) AS views, s.mv AS mv, s.items AS items,
       f.n AS fb, f.clicked AS clicked, f.purchased AS purchased, f.latency AS latency, f.served_by AS served_by
FROM (SELECT * FROM shop.requests WHERE ts::DateTime64(3) > now64(3) - INTERVAL 3 MINUTE ORDER BY ts::DateTime64(3) DESC LIMIT 60) r
LEFT JOIN (SELECT request_id::String AS rid, any(model_version::String) AS mv, any(items::Array(String)) AS items
           FROM {{TEAM}}.submissions WHERE request_id::String IN {REQ} GROUP BY rid) s ON s.rid = r.request_id::String
LEFT JOIN (SELECT request_id::String AS rid, count() AS n, any(clicked::String) AS clicked, any(purchased::String) AS purchased,
                  any(toFloat64OrZero(toString(latency_ms))) AS latency, any(served_by::String) AS served_by
           FROM {{TEAM}}.feedback WHERE ts::DateTime64(3) > now64(3) - INTERVAL 4 MINUTE GROUP BY rid) f ON f.rid = r.request_id::String
ORDER BY r.ts::DateTime64(3) DESC""",
    "minutes": """
SELECT toStartOfMinute(ts::DateTime64(3))::String AS m, count() AS n, countIf(clicked::String != '') AS clicks,
       countIf(purchased::String != '') AS buys, round(sum(toFloat64OrZero(toString(revenue_eur))), 2) AS revenue,
       quantile(0.5)(toFloat64OrZero(toString(latency_ms))) AS p50
FROM {TEAM}.feedback WHERE ts::DateTime64(3) > now64(3) - INTERVAL 120 MINUTE GROUP BY m ORDER BY m""",
    "slots": """
SELECT indexOf(shown::Array(String), clicked::String) AS slot, count() AS n
FROM {TEAM}.feedback WHERE ts::DateTime64(3) > now64(3) - INTERVAL 60 MINUTE AND clicked::String != ''
GROUP BY slot ORDER BY slot""",
    "today": """
SELECT count() AS n, countIf(served_by::String = 'team') AS on_time, countIf(purchased::String != '') AS buys,
       round(sum(toFloat64OrZero(toString(revenue_eur))), 2) AS revenue, uniqExact(model_version::String) AS labels
FROM {TEAM}.feedback WHERE ts::DateTime64(3) >= toStartOfDay(now64(3))""",
    "arms": """
SELECT model_version::String AS mv, count() AS n FROM {TEAM}.feedback
WHERE ts::DateTime64(3) > now64(3) - INTERVAL 15 MINUTE AND served_by::String = 'team' GROUP BY mv ORDER BY n DESC""",
    "insights": "SELECT * FROM {TEAM}.scratch WHERE kind::String = 'insight' ORDER BY ts::String DESC LIMIT 15",
    "insight_count": "SELECT count() AS n, sum(toInt64OrZero(toString(mcp_calls))) AS mcp FROM {TEAM}.scratch WHERE kind::String = 'insight'",
    "questions": """
SELECT count() AS open FROM (SELECT DISTINCT id::String AS q FROM {TEAM}.scratch WHERE kind::String = 'question')
WHERE q NOT IN (SELECT id::String FROM {TEAM}.scratch WHERE kind::String = 'insight')""",
}
EVERY = {"insights": 15, "insight_count": 15, "questions": 15}   # slower-moving sources, seconds

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
                rows = rt.query(sql + LIMIT, timeout=15)
                cache[key] = {"rows": rows, "at": time.time(), "error": "", "ms": round(1000 * (time.time() - t)), "tried": t}
            except Exception as e:   # keep the last good rows, say how old they are
                cache[key] = {**old, "error": str(e)[:160].split("\n")[0], "tried": t}
                cache[key].setdefault("rows", [])
        time.sleep(max(0.5, 5 - (time.time() - start)))


def route(r: dict) -> str:
    if not r["views"]:
        return "home"
    return "new" if r["new_user"] else "returning"


def stream(rows: list[dict]) -> list[dict]:
    """Newest first: at most 4 still waiting for feedback, then answered ones, 25 in all."""
    pending = [r for r in rows if not r.get("fb")][:4]
    rows = sorted(pending + [r for r in rows if r.get("fb")], key=lambda r: r["ts"], reverse=True)[:25]
    out = []
    for r in rows:
        items = r.get("items") or []
        out.append({"ts": r["ts"][11:19], "id": r["rid"][2:8], "rid": r["rid"], "route": route(r), "label": name_of(r.get("mv") or ""),
                    "items": [{"p": p, "c": categories.get(p, "?"), "clicked": p == r.get("clicked"), "bought": p == r.get("purchased")} for p in items],
                    "feedback": bool(r.get("fb")), "on_time": r.get("served_by") == "team", "latency": r.get("latency") or 0})
    return out


def scratch_text(v) -> str:
    return v if isinstance(v, str) else "" if v is None else json.dumps(v)


def insights(rows: list[dict]) -> list[dict]:
    keys = ("ts", "agent", "source", "question", "finding", "verdict")
    return [{**{k: scratch_text(r.get(k)) for k in keys}, "ts": scratch_text(r.get("ts"))[:16],
             "mcp_calls": int(r.get("mcp_calls") or 0) if str(r.get("mcp_calls") or "0").isdigit() else 0} for r in rows]


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
        "now": time.strftime("%H:%M:%S", time.gmtime(now)),
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
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/" or path.startswith("/static/"):
            self.path = "/index.html" if path == "/" else path[len("/static"):]
            if self.path.lstrip("/") not in ("index.html", "style.css", "app.js"):
                self.send_error(404)
                return
            super().do_GET()
        else:
            self.send_error(404)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    threading.Thread(target=refresh, daemon=True).start()
    port = int(os.environ.get("PORT", 8787))
    print(f"http://127.0.0.1:{port}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
