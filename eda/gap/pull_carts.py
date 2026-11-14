"""History carts of shoppers who made requests today: per (user, product) carts, last cart time, views, bought.

    uv run python eda/gap/pull_carts.py   -> data/gap/hcart.parquet
"""
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from q2q import rt

N = 8
SQL = """SELECT user_id::String AS user_id, product_id::String AS product_id, countIf(event_type::String = 'add_to_cart') AS carts,
       toUnixTimestamp64Milli(maxIf(ts::DateTime64(3, 'UTC'), event_type::String = 'add_to_cart')) AS last_cart,
       countIf(event_type::String = 'view') AS views, countIf(event_type::String = 'purchase') AS buys
FROM shop.history_events
WHERE cityHash64(user_id::String) % {N} = {c}
  AND user_id::String IN (SELECT user_id::String FROM shop.requests WHERE cityHash64(user_id::String) % {N} = {c})
GROUP BY user_id, product_id HAVING carts > 0 AND buys = 0"""

if __name__ == "__main__":
    with ThreadPoolExecutor(4) as pool:
        df = pd.concat(pool.map(lambda c: pd.DataFrame(rt.query(SQL.replace("{N}", str(N)).replace("{c}", str(c)), timeout=60)), range(N)), ignore_index=True)
    df.to_parquet(rt.ROOT / "data" / "gap" / "hcart.parquet")
    print(len(df), df.user_id.nunique())
