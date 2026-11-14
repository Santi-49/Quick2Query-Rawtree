"""H-gap pulls: our feedback joined to its request, and today's organic events of shoppers who made requests.

    uv run python eda/gap/pull.py      -> data/gap/fb.parquet, data/gap/ev.parquet
"""
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from q2q import rt

OUT = rt.ROOT / "data" / "gap"
N = 8
FB = """SELECT f.id AS request_id, r.u AS user_id, r.t AS req_ts, r.new AS is_new, r.page AS page, r.device AS device, r.region AS region,
       r.views AS views, r.vts AS view_ts, f.shown AS shown, f.clicked AS clicked, f.purchased AS purchased, f.mv AS model_version,
       f.served AS served_by, f.lat AS latency_ms, f.rev AS revenue
FROM (SELECT request_id::String AS id, shown::Array(String) AS shown, clicked::String AS clicked, purchased::String AS purchased,
             model_version::String AS mv, served_by::String AS served, latency_ms::Int64 AS lat, revenue_eur::Float64 AS rev
      FROM {TEAM}.feedback) AS f
INNER JOIN (SELECT request_id::String AS id, user_id::String AS u, toUnixTimestamp64Milli(ts::DateTime64(3, 'UTC')) AS t, is_new_user::Bool AS new,
                   context.page::String AS page, context.device::String AS device, context.region::String AS region,
                   arrayMap(v -> v.product_id::String, recent_views::Array(JSON)) AS views,
                   arrayMap(v -> toUnixTimestamp64Milli(v.ts::DateTime64(3, 'UTC')), recent_views::Array(JSON)) AS vts
            FROM shop.requests WHERE cityHash64(user_id::String) % {N} = {c}) AS r ON f.id = r.id"""
EV = """SELECT user_id::String AS user_id, session_id::String AS session_id, event_type::String AS et, product_id::String AS product_id,
       price_eur::Float64 AS price, toUnixTimestamp64Milli(ts::DateTime64(3, 'UTC')) AS ts
FROM shop.events
WHERE cityHash64(user_id::String) % {N} = {c}
  AND user_id::String IN (SELECT user_id::String FROM shop.requests WHERE cityHash64(user_id::String) % {N} = {c})"""


def pull(sql: str) -> pd.DataFrame:
    with ThreadPoolExecutor(4) as pool:
        parts = pool.map(lambda c: pd.DataFrame(rt.query(sql.replace("{N}", str(N)).replace("{c}", str(c)), timeout=60)), range(N))
        return pd.concat(list(parts), ignore_index=True)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    fb = pull(FB)
    fb.to_parquet(OUT / "fb.parquet")
    print("fb", len(fb), (fb.purchased != "").sum())
    ev = pull(EV)
    ev.to_parquet(OUT / "ev.parquet")
    print("ev", len(ev), ev.et.value_counts().to_dict())
