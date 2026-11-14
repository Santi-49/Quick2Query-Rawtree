"""RawTree pulls for the ML pattern study, cached as parquet under data/ml/ (read-only SELECTs).

History rows: carousel requests in [CUT_H, END) of shoppers with cityHash64(user) % 5 = 0; their shopper and product
aggregates use organic events before CUT_H only. Live rows: every feedback row; aggregates use all history (< END).
"""
import json
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

from q2q import rt

ML = rt.ROOT / "data" / "ml"
CUT_H, END = "2026-11-04 07:00:00", "2026-11-14 07:00:00"
HIST_USERS = "cityHash64(user_id::String) % 5 = 0"
LIVE_USERS = "user_id::String IN (SELECT user_id::String FROM shop.requests)"
EV = "(SELECT user_id::String AS u, session_id::String AS s, event_type::String AS e, product_id::String AS p, ts::DateTime64(3) AS t, device::String AS dev, region::String AS reg FROM shop.history_events WHERE ts::DateTime64(3) < '{CUT}' AND {UF})"

SQL = {
    "catalog": """SELECT product_id::String AS p, category::String AS cat, subcategory::String AS sub, brand::String AS brand, price_eur::Float64 AS price,
        description::String AS descr, toUnixTimestamp(created_at::DateTime64(3)) AS created, 0 AS is_new FROM shop.catalog
        UNION ALL SELECT product_id::String, any(category::String), any(subcategory::String), any(brand::String), any(price_eur::Float64), any(description::String),
        toUnixTimestamp(min(ts::DateTime64(3))), 1 FROM shop.catalog_updates WHERE change::String = 'new_product' GROUP BY product_id::String""",
    "updates": """SELECT toUnixTimestamp64Milli(ts::DateTime64(3, 'UTC')) / 1000 AS t, product_id::String AS p, change::String AS change, price_eur::Float64 AS price
        FROM shop.catalog_updates""",
    "products": """SELECT p, countIf(e = 'view') AS v, countIf(e = 'add_to_cart') AS c, countIf(e = 'purchase') AS b, uniqExactIf(u, e = 'view') AS viewers,
        countIf(e = 'view' AND t >= toDateTime64('{CUT}', 3) - INTERVAL 7 DAY) AS v7, countIf(e = 'purchase' AND t >= toDateTime64('{CUT}', 3) - INTERVAL 7 DAY) AS b7
        FROM """ + EV.replace("{UF}", "1") + " GROUP BY p",
    "carousel": """SELECT p, count() AS imp, sum(1 / log2(k + 1)) AS w, countIf(ck = p) AS clk, countIf(pu = p) AS buy FROM (
        SELECT arrayJoin(arrayEnumerate(shown::Array(String))) AS k, (shown::Array(String))[k] AS p, ifNull(clicked::String, '') AS ck, ifNull(purchased::String, '') AS pu
        FROM shop.history_sessions WHERE ts::DateTime64(3) < '{CUT}') GROUP BY p""",
    "users": """SELECT u, any(dev) AS dev, any(reg) AS reg, count() AS ns, avg(n) AS sl_mean, max(n) AS sl_max, stddevPop(n) AS sl_sd, avg(dur) AS sdur_mean,
        uniqExact(d) AS nd, toUnixTimestamp(max(t1)) AS last, toUnixTimestamp(min(t0)) AS first, avg(h) AS hour_mean, stddevPop(h) AS hour_sd, avg(we) AS weekend,
        avg(nbuy > 0) AS sess_buy_rate, avg(ncart > 0) AS sess_cart_rate
        FROM (SELECT u, s, any(dev) AS dev, any(reg) AS reg, count() AS n, dateDiff('second', min(t), max(t)) AS dur, toDate(min(t)) AS d, min(t) AS t0, max(t) AS t1,
              toHour(min(t)) AS h, toDayOfWeek(min(t)) >= 6 AS we, countIf(e = 'purchase') AS nbuy, countIf(e = 'add_to_cart') AS ncart FROM """ + EV + """ GROUP BY u, s)
        GROUP BY u""",
    "up": """SELECT u, p, countIf(e = 'view') AS v, countIf(e = 'add_to_cart') AS c, countIf(e = 'purchase') AS b,
        toUnixTimestamp(maxIf(t, e = 'view')) AS lv, toUnixTimestamp(maxIf(t, e = 'purchase')) AS lb FROM """ + EV.replace("{UF}", "{UF} AND cityHash64(user_id::String) % {N} = {K}") + " GROUP BY u, p",
    "coview": """SELECT a, b, count() AS n FROM (SELECT product_id::String AS b, lagInFrame(product_id::String) OVER (PARTITION BY session_id::String ORDER BY ts::DateTime64(3)
        ROWS BETWEEN 1 PRECEDING AND CURRENT ROW) AS a FROM shop.history_events WHERE event_type::String = 'view' AND ts::DateTime64(3) < '{CUT}'
        AND cityHash64(session_id::String) % {N} = {K}) WHERE a != '' AND a != b GROUP BY a, b""",
    "imp_live": """SELECT f.rid AS rid, r.t AS t, f.shown AS shown, f.clicked AS clicked, f.purchased AS purchased, r.u AS u, r.new AS new, r.page AS page, r.dev AS dev,
        r.reg AS reg, r.vp AS vp, r.vt AS vt, s.mv AS mv
        FROM (SELECT request_id::String AS rid, any(shown::Array(String)) AS shown, any(clicked::String) AS clicked, any(purchased::String) AS purchased
              FROM {TEAM}.feedback WHERE cityHash64(request_id::String) % {N} = {K} GROUP BY rid) f
        INNER JOIN (SELECT request_id::String AS rid, any(user_id::String) AS u, any(is_new_user::Bool) AS new, any(context.page::String) AS page,
              any(context.device::String) AS dev, any(context.region::String) AS reg, any(arrayMap(v -> v.product_id::String, recent_views::Array(JSON))) AS vp,
              any(arrayMap(v -> toUnixTimestamp64Milli(v.ts::DateTime64(3, 'UTC')) / 1000, recent_views::Array(JSON))) AS vt,
              any(toUnixTimestamp64Milli(ts::DateTime64(3, 'UTC')) / 1000) AS t FROM shop.requests WHERE cityHash64(request_id::String) % {N} = {K} GROUP BY rid) r ON r.rid = f.rid
        LEFT JOIN (SELECT request_id::String AS rid, any(model_version::String) AS mv FROM {TEAM}.submissions WHERE cityHash64(request_id::String) % {N} = {K} GROUP BY rid) s ON s.rid = f.rid""",
    "imp_hist": """SELECT request_id::String AS rid, toUnixTimestamp64Milli(ts::DateTime64(3, 'UTC')) / 1000 AS t, shown::Array(String) AS shown,
        ifNull(clicked::String, '') AS clicked, ifNull(purchased::String, '') AS purchased, user_id::String AS u, false AS new, context.page::String AS page,
        context.device::String AS dev, context.region::String AS reg, arrayMap(v -> v.product_id::String, recent_views::Array(JSON)) AS vp,
        arrayMap(v -> toUnixTimestamp64Milli(v.ts::DateTime64(3, 'UTC')) / 1000, recent_views::Array(JSON)) AS vt, 'carousel' AS mv
        FROM shop.history_sessions WHERE ts::DateTime64(3) >= '""" + CUT_H + "' AND ts::DateTime64(3) < '" + END + "' AND " + HIST_USERS + " AND cityHash64(request_id::String) % {N} = {K}",
    "trend": """SELECT intDiv(toUnixTimestamp(ts::DateTime64(3)), 300) AS bk, product_id::String AS p, count() AS n FROM shop.events
        WHERE event_type::String = 'view' AND cityHash64(product_id::String) % {N} = {K} GROUP BY bk, p""",
}


def pull(name: str, chunks: int = 1, refresh: bool = False, **kw) -> pd.DataFrame:
    """Run SQL[name] (with {CUT}/{UF} from kw) over `chunks` hash chunks, 4 at a time; cache as data/ml/<name>[_tag].parquet."""
    tag = kw.pop("tag", "")
    path = ML / f"{name}{'_' + tag if tag else ''}.parquet"
    if path.exists() and not refresh:
        return pd.read_parquet(path)
    sql = SQL[name]
    for k, v in kw.items():
        sql = sql.replace("{" + k + "}", v)
    start = time.time()

    def one(k):
        for attempt in range(3):
            try:
                return pd.DataFrame(rt.query(sql.replace("{N}", str(chunks)).replace("{K}", str(k)), timeout=60))
            except Exception as e:  # noqa: BLE001 - transient HTTP errors: retry
                if attempt == 2:
                    raise
                print(f"  {name} chunk {k}: {str(e)[:120]}, retrying")
    with ThreadPoolExecutor(4) as pool:
        df = pd.concat(list(pool.map(one, range(chunks))), ignore_index=True)
    ML.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path)
    print(f"pulled {path.name}: {len(df):,} rows in {time.time() - start:.0f} s", flush=True)
    return df


def pull_all(refresh: bool = False) -> dict:
    """Everything build.py needs. Live tables (imp_live, trend, updates, catalog) are refreshed when refresh=True."""
    out = {"catalog": pull("catalog", refresh=refresh), "updates": pull("updates", refresh=refresh),
           "imp_live": pull("imp_live", 8, refresh=refresh), "trend": pull("trend", 4, refresh=refresh),
           "imp_hist": pull("imp_hist", 16), "coview": pull("coview", 16, CUT=CUT_H)}
    for tag, cut, uf, n in (("h", CUT_H, HIST_USERS, 16), ("l", END, LIVE_USERS, 32)):
        out["products_" + tag] = pull("products", CUT=cut, tag=tag)
        out["carousel_" + tag] = pull("carousel", CUT=cut, tag=tag)
        out["users_" + tag] = pull("users", 1, CUT=cut, UF=uf, tag=tag).drop_duplicates("u")
        out["up_" + tag] = pull("up", n, CUT=cut, UF=uf, tag=tag)
    out["segment"] = pd.DataFrame(json.loads((rt.ROOT / "data" / "segment_category.json").read_text(encoding="utf-8")))
    return out


if __name__ == "__main__":
    d = pull_all()
    print({k: len(v) for k, v in d.items()}, np.round(sum(v.memory_usage(deep=True).sum() for v in d.values()) / 2**20), "MiB")
