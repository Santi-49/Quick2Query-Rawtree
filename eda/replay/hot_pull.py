"""Pull for eda/replay/hot1.py: home requests (no recent views) of today, their shoppers' buys and views, live
product counts per 10 minutes, cached under data/replay/hot_*.parquet (read-only SELECTs).

    uv run eda/replay/hot_pull.py [START]      # default 09:30 UTC today, end = newest request

Frames:
  reqs     every home request we got feedback for (route no_views), as pull.py
  buys     purchases (shop.events organic, our feedback) of those shoppers, up to end + 30 min
  today    their views (from start - 2 h) and every cart, up to end
  counts   shop.events per product, 10-minute bucket, event type (and region, device for carts and purchases)
  meta     start, end
"""
import importlib.util
import sys

import pandas as pd

from q2q import rt

DIR = rt.ROOT / "data" / "replay"
spec = importlib.util.spec_from_file_location("replay_pull", rt.ROOT / "eda" / "replay" / "pull.py")
pull = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pull)

HOME = "length(recent_views::Array(JSON)) = 0"
COUNTS = """SELECT product_id::String AS p, toUInt32(toUnixTimestamp(ts::DateTime64(3)) / 600) AS b, event_type::String AS e,
  {DIM} AS d, count() AS n FROM shop.events WHERE {WHERE} AND cityHash64(product_id::String) % 4 = {K} GROUP BY p, b, e, d"""


def counts(dim: str, where: str) -> pd.DataFrame:
    sql = COUNTS.replace("{DIM}", dim).replace("{WHERE}", where)
    return pd.concat([pd.DataFrame(rt.query(sql.replace("{K}", str(k)), timeout=120)) for k in range(4)], ignore_index=True)


def main(start: str) -> None:
    end = rt.query("SELECT toString(max(ts::DateTime64(3))) AS m FROM shop.requests")[0]["m"][:19]
    pull.SQL["reqs"] = pull.SQL["reqs"].replace("AND cityHash64(request_id::String) % {N} = {K} GROUP BY rid) r",
                                                f"AND {HOME} AND cityHash64(request_id::String) % {{N}} = {{K}} GROUP BY rid) r")
    pull.USERS = pull.USERS.replace("ts::DateTime64(3) < '{END}'", f"ts::DateTime64(3) < '{{END}}' AND {HOME}")
    for k in ("events", "today"):
        pull.SQL[k] = pull.SQL[k].split("AND user_id::String IN")[0] + "AND " + pull.USERS
    reqs = pull.run("reqs", start, end).sort_values("t", ignore_index=True)
    buys = pd.concat([pull.run("events", start, end).assign(organic=True), pull.run("fed", start, end).assign(organic=False)], ignore_index=True)
    out = {"reqs": reqs, "buys": buys.sort_values("t", ignore_index=True), "today": pull.run("today", start, end).sort_values("t", ignore_index=True),
           "counts": pd.concat([counts("''", "1"), counts("'r:' || region::String", "event_type::String != 'view'"),
                                counts("'d:' || device::String", "event_type::String != 'view'")], ignore_index=True),
           "meta": pd.DataFrame([{"start": start, "end": end}])}
    for k, df in out.items():
        df.to_parquet(DIR / f"hot_{k}.parquet")
    print(f"pulled {start} to {end}: {len(reqs):,} home requests, {len(buys):,} buys, {len(out['today']):,} views and carts, {len(out['counts']):,} counts")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "2026-11-14 09:30:00")
