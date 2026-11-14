"""Pull what H-home-who needs into data/home/ (read-only SELECTs). docs/hypotheses/H-home-who.md.

    uv run eda/home/pull.py

  reqs     every live request with our feedback, and the shopper's shop.events around it:
           before (today, earlier) and in the 30 min after, plus history counts
  buys     every organic purchase today (shop.events)
  carts    every add_to_cart today
  views    views today of shoppers who had a home request
  lastsess products of each home shopper's last history session
  lastbuy  each home shopper's last history purchase
  updates  shop.catalog_updates (new products, price changes)
"""
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from q2q import rt

DIR = rt.ROOT / "data" / "home"
T = "toUnixTimestamp64Milli(ts::DateTime64(3, 'UTC')) / 1000"
HOME_USERS = "user_id::String IN (SELECT user_id::String FROM shop.requests WHERE length(recent_views::Array(JSON)) = 0)"
SQL = {
    "reqs": f"""
WITH r AS (SELECT request_id::String AS rid, any(user_id::String) AS u, any(is_new_user::Bool) AS new, any(context.page::String) AS page,
                  any(context.device::String) AS dev, any(context.region::String) AS reg, any(length(recent_views::Array(JSON))) AS nrv, any({T}) AS t
           FROM shop.requests WHERE cityHash64(user_id::String) % {{N}} = {{K}} GROUP BY rid),
     f AS (SELECT request_id::String AS rid, any(shown::Array(String)) AS shown, any(clicked::String) AS clicked, any(purchased::String) AS purchased,
                  any(served_by::String) AS served FROM {{TEAM}}.feedback GROUP BY rid),
     s AS (SELECT request_id::String AS rid, any(model_version::String) AS mv FROM {{TEAM}}.submissions GROUP BY rid),
     e AS (SELECT user_id::String AS u, {T} AS et, event_type::String AS ty, session_id::String AS ss, product_id::String AS p
           FROM shop.events WHERE cityHash64(user_id::String) % {{N}} = {{K}}),
     h AS (SELECT user_id::String AS u, count() AS h_ev, countIf(event_type::String = 'purchase') AS h_buys,
                  countIf(event_type::String = 'add_to_cart') AS h_carts, uniqExact(session_id::String) AS h_sess, max({T}) AS h_last
           FROM shop.history_events WHERE cityHash64(user_id::String) % {{N}} = {{K}} GROUP BY u),
     ea AS (SELECT r.rid AS rid,
                countIf(e.et < r.t) AS ev_before, countIf(e.ty = 'view' AND e.et < r.t) AS views_before,
                countIf(e.ty = 'add_to_cart' AND e.et < r.t) AS carts_before, countIf(e.ty = 'purchase' AND e.et < r.t) AS buys_before,
                maxIf(e.et, e.et < r.t) AS last_t, argMaxIf(e.ty, e.et, e.et < r.t) AS last_ty, argMaxIf(e.ss, e.et, e.et < r.t) AS last_ss,
                maxIf(e.et, e.ty = 'purchase' AND e.et < r.t) AS last_buy_t,
                minIf(e.et, e.et >= r.t) AS next_t, argMinIf(e.ty, e.et, e.et >= r.t) AS next_ty, argMinIf(e.ss, e.et, e.et >= r.t) AS next_ss,
                countIf(e.ty = 'view' AND e.et >= r.t AND e.et < r.t + 1800) AS views_30,
                countIf(e.ty = 'add_to_cart' AND e.et >= r.t AND e.et < r.t + 1800) AS carts_30,
                countIf(e.ty = 'purchase' AND e.et >= r.t AND e.et < r.t + 1800) AS buys_30,
                countIf(e.ty = 'purchase' AND e.et >= r.t AND e.et < r.t + 600) AS buys_10,
                argMinIf(e.p, e.et, e.ty = 'purchase' AND e.et >= r.t AND e.et < r.t + 1800) AS buy_p,
                minIf(e.et, e.ty = 'purchase' AND e.et >= r.t AND e.et < r.t + 1800) AS buy_t,
                argMinIf(e.p, e.et, e.ty = 'view' AND e.et >= r.t AND e.et < r.t + 1800) AS view_p
            FROM r INNER JOIN e ON e.u = r.u GROUP BY r.rid)
SELECT r.*, f.shown AS shown, f.clicked AS clicked, f.purchased AS purchased, f.served AS served, s.mv AS mv,
       ea.ev_before, ea.views_before, ea.carts_before, ea.buys_before, ea.last_t, ea.last_ty, ea.last_ss, ea.last_buy_t,
       ea.next_t, ea.next_ty, ea.next_ss, ea.views_30, ea.carts_30, ea.buys_30, ea.buys_10, ea.buy_p, ea.buy_t, ea.view_p,
       h.h_ev AS h_ev, h.h_buys AS h_buys, h.h_carts AS h_carts, h.h_sess AS h_sess, h.h_last AS h_last
FROM r INNER JOIN f ON f.rid = r.rid LEFT JOIN s ON s.rid = r.rid LEFT JOIN ea ON ea.rid = r.rid LEFT JOIN h ON h.u = r.u""",
    "buys": f"SELECT user_id::String AS u, product_id::String AS p, {T} AS t, price_eur::Float64 AS price, device::String AS dev, region::String AS reg "
            "FROM shop.events WHERE event_type::String = 'purchase' AND cityHash64(user_id::String) % {N} = {K}",
    "carts": f"SELECT user_id::String AS u, product_id::String AS p, {T} AS t FROM shop.events "
             "WHERE event_type::String = 'add_to_cart' AND cityHash64(user_id::String) % {N} = {K}",
    "views": f"SELECT user_id::String AS u, product_id::String AS p, {T} AS t FROM shop.events "
             f"WHERE event_type::String = 'view' AND cityHash64(user_id::String) % {{N}} = {{K}} AND {HOME_USERS}",
    "lastsess": f"""SELECT h.u AS u, h.p AS p, h.ty AS ty FROM
        (SELECT user_id::String AS u, session_id::String AS ss, product_id::String AS p, event_type::String AS ty FROM shop.history_events
         WHERE cityHash64(user_id::String) % {{N}} = {{K}} AND {HOME_USERS}) h
        INNER JOIN (SELECT user_id::String AS u, argMax(session_id::String, ts::DateTime64(3)) AS ss FROM shop.history_events
         WHERE cityHash64(user_id::String) % {{N}} = {{K}} AND {HOME_USERS} GROUP BY u) l ON l.u = h.u AND l.ss = h.ss""",
    "lastbuy": f"SELECT user_id::String AS u, argMax(product_id::String, ts::DateTime64(3)) AS p FROM shop.history_events "
               f"WHERE event_type::String = 'purchase' AND cityHash64(user_id::String) % {{N}} = {{K}} AND {HOME_USERS} GROUP BY u",
    "updates": f"SELECT change::String AS change, product_id::String AS p, category::String AS category, subcategory::String AS subcategory, "
               f"brand::String AS brand, price_eur::Float64 AS price, {T} AS t FROM shop.catalog_updates WHERE cityHash64(product_id::String) % {{N}} = {{K}}",
}
CHUNKS = {"reqs": 16, "buys": 2, "carts": 2, "views": 16, "lastsess": 8, "lastbuy": 4, "updates": 1}


def run(name: str) -> pd.DataFrame:
    def one(k):
        for attempt in range(3):
            try:
                return pd.DataFrame(rt.query(SQL[name].replace("{N}", str(CHUNKS[name])).replace("{K}", str(k)), timeout=120))
            except Exception as e:  # noqa: BLE001 - transient HTTP errors: retry
                if attempt == 2:
                    raise
                print(f"  {name} chunk {k}: {str(e)[:200]}, retrying", flush=True)
    with ThreadPoolExecutor(4) as pool:
        return pd.concat(list(pool.map(one, range(CHUNKS[name]))), ignore_index=True)


if __name__ == "__main__":
    DIR.mkdir(parents=True, exist_ok=True)
    for name in sys.argv[1:] or SQL:
        start = time.time()
        df = run(name)
        df.to_parquet(DIR / f"{name}.parquet")
        print(f"{name}: {len(df):,} rows in {time.time() - start:.0f} s", flush=True)
