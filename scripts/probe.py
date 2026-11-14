# /// script
# requires-python = ">=3.10"
# dependencies = ["requests"]
# ///
"""One-off probe of the RawTree databases. Read-only except one marker row in team scratch.

    uv run scripts/probe.py        # writes docs/findings/00-probe.md

Every query is independent: a failure is recorded and the probe continues.
"""
import json
import os
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
for line in (ROOT / ".env").read_text().splitlines():
    key, _, value = line.partition("=")
    if value and not key.startswith("#"):
        os.environ.setdefault(key.strip(), value.strip())
API = os.environ.get("RAWTREE_API_URL", "https://api.rawtree.com")
TEAM = os.environ["TEAM_ID"]
http = requests.Session()
http.headers["Authorization"] = f"Bearer {os.environ['RAWTREE_API_KEY']}"

NOT_EMPTY = "isNotNull({c}) AND {c}::String != ''"
CLICKED, BOUGHT = NOT_EMPTY.format(c="clicked"), NOT_EMPTY.format(c="purchased")

QUERIES = {
    # shapes
    "sample catalog": "SELECT * FROM shop.catalog LIMIT 2",
    "sample history_sessions": "SELECT * FROM shop.history_sessions LIMIT 1",
    "sample history_events": "SELECT * FROM shop.history_events LIMIT 2",
    "sample requests": "SELECT * FROM shop.requests ORDER BY ts DESC LIMIT 2",
    "sample events": "SELECT * FROM shop.events ORDER BY ts DESC LIMIT 2",
    "sample catalog_updates": "SELECT * FROM shop.catalog_updates ORDER BY ts DESC LIMIT 2",
    "sample feedback": f"SELECT * FROM {TEAM}.feedback ORDER BY ts DESC LIMIT 2",
    "sample submissions": f"SELECT * FROM {TEAM}.submissions LIMIT 2",
    "describe history_sessions": "DESCRIBE shop.history_sessions",
    "tables we can see": "SELECT database, name, total_rows FROM system.tables WHERE database IN ('shop', '" + TEAM + "')",
    # sizes and time ranges
    **{f"range {t}": f"SELECT count() AS n, min(ts) AS first, max(ts) AS last FROM shop.{t}"
       for t in ("history_sessions", "history_events", "requests", "events", "catalog_updates")},
    # catalogue
    "catalog by category": "SELECT category::String AS category, count() AS products, uniq(subcategory::String) AS subcats, "
                           "uniq(brand::String) AS brands, round(avg(price_eur::Float64), 2) AS avg_price, "
                           "countIf(is_active::Bool) AS active FROM shop.catalog GROUP BY category ORDER BY products DESC",
    "catalog price quantiles": "SELECT quantiles(0.05, 0.25, 0.5, 0.75, 0.95, 0.99)(price_eur::Float64) AS q FROM shop.catalog",
    "catalog updates by change": "SELECT change::String AS change, count() AS n FROM shop.catalog_updates GROUP BY change",
    # carousel history
    "history base rates": f"SELECT count() AS n, round(100 * countIf({CLICKED}) / count(), 2) AS ctr_pct, "
                          f"round(100 * countIf({BOUGHT}) / count(), 2) AS conv_pct, "
                          f"round(100 * countIf({BOUGHT} AND purchased::String != clicked::String) / greatest(countIf({BOUGHT}), 1), 2) "
                          "AS bought_not_clicked_pct, uniq(user_id::String) AS users FROM shop.history_sessions",
    "history clicks by slot": f"SELECT indexOf(shown, clicked) AS slot, count() AS clicks, countIf({BOUGHT}) AS purchases "
                              f"FROM shop.history_sessions WHERE {CLICKED} GROUP BY slot ORDER BY slot",
    "history by page": f"SELECT context.page::String AS page, count() AS n, round(100 * countIf({BOUGHT}) / count(), 2) AS conv_pct "
                       "FROM shop.history_sessions GROUP BY page ORDER BY n DESC",
    "history by device": f"SELECT context.device::String AS device, count() AS n, round(100 * countIf({BOUGHT}) / count(), 2) AS conv_pct "
                         "FROM shop.history_sessions GROUP BY device ORDER BY n DESC",
    "history by region": f"SELECT context.region::String AS region, count() AS n, round(100 * countIf({BOUGHT}) / count(), 2) AS conv_pct "
                         "FROM shop.history_sessions GROUP BY region ORDER BY n DESC LIMIT 30",
    "history recent_views length": "SELECT length(recent_views) AS views, count() AS n FROM shop.history_sessions GROUP BY views ORDER BY views LIMIT 25",
    "history distinct products shown": "SELECT uniq(arrayJoin(shown::Array(String))) AS products_ever_shown FROM shop.history_sessions",
    "history propensity quantiles": "SELECT quantiles(0.01, 0.1, 0.5, 0.9, 0.99)(arrayJoin(propensity::Array(Float64))) AS q FROM shop.history_sessions",
    # organic history
    "events by type": "SELECT event_type::String AS event_type, count() AS n, uniq(user_id::String) AS users, "
                      "uniq(session_id::String) AS sessions, uniq(product_id::String) AS products FROM shop.history_events GROUP BY event_type",
    # live stream
    "live requests profile": "SELECT count() AS n, round(100 * countIf(is_new_user::Bool) / count(), 1) AS new_user_pct, "
                             "round(100 * countIf(length(recent_views) = 0) / count(), 1) AS no_views_pct, "
                             "round(avg(length(recent_views)), 2) AS avg_views, uniq(user_id::String) AS users FROM shop.requests",
    "live requests by page": "SELECT context.page::String AS page, count() AS n FROM shop.requests GROUP BY page ORDER BY n DESC",
    "live rate last 10 min": "SELECT (SELECT count() FROM shop.requests WHERE ts::DateTime64(3) > now() - INTERVAL 10 MINUTE) / 600 AS requests_per_s, "
                             "(SELECT count() FROM shop.events WHERE ts::DateTime64(3) > now() - INTERVAL 10 MINUTE) / 600 AS events_per_s",
    "live users known in history": "SELECT count() AS live_users, countIf(user_id IN (SELECT DISTINCT user_id::String FROM shop.history_events)) AS in_history "
                                   "FROM (SELECT DISTINCT user_id::String AS user_id FROM shop.requests WHERE NOT is_new_user::Bool)",
    # our results so far
    "feedback summary": f"SELECT served_by::String AS served_by, fallback_reason::String AS reason, count() AS n, "
                        "round(100 * countIf(clicked::String != '') / count(), 2) AS ctr_pct, "
                        "round(100 * countIf(purchased::String != '') / count(), 2) AS conv_pct, "
                        "round(sum(revenue_eur::Float64) / count(), 3) AS eur_per_request, "
                        "round(quantile(0.5)(latency_ms::Float64)) AS p50_ms, round(quantile(0.95)(latency_ms::Float64)) AS p95_ms "
                        f"FROM {TEAM}.feedback WHERE request_id::String != '__init__' GROUP BY served_by, reason",
}


def run(sql: str) -> tuple[str, float]:
    start = time.time()
    try:
        r = http.post(f"{API}/v1/query", json={"sql": sql}, timeout=120)
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {"raw": r.text[:2000]}
        out = body.get("data", body) if r.ok else {"http": r.status_code, "error": body}
    except Exception as e:  # keep probing
        out = {"exception": repr(e)}
    return json.dumps(out, indent=1, ensure_ascii=False, default=str)[:6000], time.time() - start


def main() -> None:
    parts = [f"# RawTree probe · {time.strftime('%Y-%m-%d %H:%M:%S')} · {TEAM}\n"]
    for title, sql in QUERIES.items():
        out, seconds = run(sql)
        print(f"{seconds:6.2f}s  {title}")
        parts.append(f"## {title}\n\n`{seconds:.2f}s`\n\n```sql\n{sql}\n```\n\n```json\n{out}\n```\n")

    # Can we create our own tables? Insert one marker row into a new table and into scratch.
    for table in ("scratch", "probe_marker"):
        try:
            r = http.post(f"{API}/v1/tables/{table}", params={"database": TEAM},
                          json=[{"kind": "probe", "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}], timeout=30)
            parts.append(f"## insert into {TEAM}.{table}\n\nHTTP {r.status_code}: `{r.text[:300]}`\n")
        except Exception as e:
            parts.append(f"## insert into {TEAM}.{table}\n\n`{e!r}`\n")

    out_file = ROOT / "docs" / "findings" / "00-probe.md"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text("\n".join(parts), encoding="utf-8")
    print(f"written {out_file}")


if __name__ == "__main__":
    main()
