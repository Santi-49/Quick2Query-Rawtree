"""Pull the logged requests of the last N hours for replay, cached as parquet under data/replay/ (read-only SELECTs).

    uv run eda/replay/pull.py 4          # or through q2q replay, which calls pull(hours)

Four frames, all for the window [start, end) where end is the newest request at pull time:
  reqs   one row per request we got feedback for: Request fields, the list shown, click, purchase, served_by, model_version
  buys   purchases with time (shop.events and our feedback) of the window's shoppers, up to end + 30 min:
         live purchases before a request feed the State, organic ones after it feed organic@10
  today  views (from start - 2 h) and every cart in shop.events of the window's shoppers, up to end: the State's "today"
  meta   start, end
"""
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import pandas as pd

from q2q import rt

DIR = rt.ROOT / "data" / "replay"
T = "toUnixTimestamp64Milli(ts::DateTime64(3, 'UTC')) / 1000"
USERS = "user_id::String IN (SELECT user_id::String FROM shop.requests WHERE ts::DateTime64(3) >= '{START}' AND ts::DateTime64(3) < '{END}')"
SQL = {
    "reqs": f"""SELECT r.rid AS rid, r.t AS t, r.u AS u, r.new AS new, r.page AS page, r.dev AS dev, r.reg AS reg, r.vp AS vp,
        f.shown AS shown, f.clicked AS clicked, f.purchased AS purchased, f.served AS served, s.mv AS mv
        FROM (SELECT request_id::String AS rid, any(user_id::String) AS u, any(is_new_user::Bool) AS new, any(context.page::String) AS page,
              any(context.device::String) AS dev, any(context.region::String) AS reg, any(arrayMap(v -> v.product_id::String, recent_views::Array(JSON))) AS vp,
              any({T}) AS t FROM shop.requests
              WHERE ts::DateTime64(3) >= '{{START}}' AND ts::DateTime64(3) < '{{END}}' AND cityHash64(request_id::String) % {{N}} = {{K}} GROUP BY rid) r
        INNER JOIN (SELECT request_id::String AS rid, any(shown::Array(String)) AS shown, any(clicked::String) AS clicked, any(purchased::String) AS purchased,
              any(served_by::String) AS served FROM {{TEAM}}.feedback
              WHERE ts::DateTime64(3) >= toDateTime64('{{START}}', 3) - INTERVAL 1 MINUTE AND cityHash64(request_id::String) % {{N}} = {{K}} GROUP BY rid) f ON f.rid = r.rid
        LEFT JOIN (SELECT request_id::String AS rid, any(model_version::String) AS mv FROM {{TEAM}}.submissions
              WHERE cityHash64(request_id::String) % {{N}} = {{K}} GROUP BY rid) s ON s.rid = r.rid""",
    "events": f"""SELECT user_id::String AS u, product_id::String AS p, {T} AS t FROM shop.events
        WHERE event_type::String = 'purchase' AND ts::DateTime64(3) < toDateTime64('{{END}}', 3) + INTERVAL 30 MINUTE
          AND cityHash64(user_id::String) % {{N}} = {{K}} AND {USERS}""",
    "fed": f"""SELECT r.u AS u, f.p AS p, f.t AS t FROM
        (SELECT request_id::String AS rid, any(purchased::String) AS p, any({T}) AS t FROM {{TEAM}}.feedback
         WHERE purchased::String != '' AND ts::DateTime64(3) < '{{END}}' GROUP BY rid) f
        INNER JOIN (SELECT request_id::String AS rid, any(user_id::String) AS u FROM shop.requests GROUP BY rid) r ON r.rid = f.rid""",
    "today": f"""SELECT user_id::String AS u, product_id::String AS p, event_type::String = 'add_to_cart' AS cart, {T} AS t FROM shop.events
        WHERE (event_type::String = 'add_to_cart' OR (event_type::String = 'view' AND ts::DateTime64(3) >= toDateTime64('{{START}}', 3) - INTERVAL 2 HOUR))
          AND ts::DateTime64(3) < '{{END}}' AND cityHash64(user_id::String) % {{N}} = {{K}} AND {USERS}""",
}
CHUNKS = {"reqs": 4, "events": 4, "fed": 1, "today": 16}


def run(name: str, start: str, end: str) -> pd.DataFrame:
    sql = SQL[name].replace("{START}", start).replace("{END}", end)

    def one(k):
        for attempt in range(3):
            try:
                return pd.DataFrame(rt.query(sql.replace("{N}", str(CHUNKS[name])).replace("{K}", str(k)), timeout=60))
            except Exception as e:  # noqa: BLE001 - transient HTTP errors: retry
                if attempt == 2:
                    raise
                print(f"  {name} chunk {k}: {str(e)[:120]}, retrying", flush=True)
    with ThreadPoolExecutor(4) as pool:
        return pd.concat(list(pool.map(one, range(CHUNKS[name]))), ignore_index=True)


def pull(hours: float, refresh: bool = False) -> dict[str, pd.DataFrame]:
    """The four frames for the last `hours`, from the cache unless refresh or missing."""
    paths = {k: DIR / f"{k}_{hours:g}h.parquet" for k in ("reqs", "buys", "today", "meta")}
    if not refresh and all(p.exists() for p in paths.values()):
        return {k: pd.read_parquet(p) for k, p in paths.items()}
    started = time.time()
    end = rt.query("SELECT toString(max(ts::DateTime64(3))) AS m FROM shop.requests")[0]["m"][:19]
    start = (datetime.fromisoformat(end) - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
    reqs = run("reqs", start, end).sort_values("t", ignore_index=True)
    buys = pd.concat([run("events", start, end).assign(organic=True), run("fed", start, end).assign(organic=False)], ignore_index=True)
    out = {"reqs": reqs, "buys": buys.sort_values("t", ignore_index=True), "today": run("today", start, end).sort_values("t", ignore_index=True),
           "meta": pd.DataFrame([{"start": start, "end": end}])}
    DIR.mkdir(parents=True, exist_ok=True)
    for k, df in out.items():
        df.to_parquet(paths[k])
    print(f"pulled {start} to {end} UTC: {len(reqs):,} requests, {len(buys):,} purchases, {len(out['today']):,} views and carts "
          f"in {time.time() - started:.0f} s", flush=True)
    return out


if __name__ == "__main__":
    pull(float(sys.argv[1]) if len(sys.argv) > 1 else 4, refresh=True)
