"""History pulls from RawTree, cached under data/ (gitignored).

    cached("product_stats")  -> rows of sql/features/product_stats.sql (chunked when the SQL has {chunk})
    user_history()           -> CSR arrays of (user, product, views, buys, carts)
    pull()                   -> rebuild every cache
"""
import json
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from q2q import rt

DATA = rt.ROOT / "data"
FEATURES = ["product_stats", "segment_category", "coview"]
CHUNKS = 16


def sql(name: str) -> str:
    return (rt.ROOT / "sql" / "features" / f"{name}.sql").read_text(encoding="utf-8")


def cached(name: str, refresh: bool = False) -> list[dict]:
    path = DATA / f"{name}.json"
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    text = sql(name)
    if "{chunk}" in text:  # one query per hash chunk, as user_products
        with ThreadPoolExecutor(4) as pool:
            rows = [r for part in pool.map(lambda c: rt.query(text.replace("{chunk}", str(c)), timeout=60), range(CHUNKS)) for r in part]
    else:
        rows = rt.query(text)
    DATA.mkdir(exist_ok=True)
    path.write_text(json.dumps(rows), encoding="utf-8")
    return rows


def user_history(refresh: bool = False) -> dict[str, np.ndarray]:
    """Per user (sorted) the products touched in history: users, indptr, prod, views, buys, products."""
    path = DATA / "user_history.npz"
    if path.exists() and not refresh:
        with np.load(path) as z:
            return dict(z)
    text = sql("user_products")
    with ThreadPoolExecutor(4) as pool:
        rows = [r for chunk in pool.map(lambda c: rt.query(text.replace("{chunk}", str(c))), range(CHUNKS)) for r in chunk]
    rows.sort(key=lambda r: r["u"])
    products = np.array(sorted({p for r in rows for p in r["prods"]}))
    index = {p: i for i, p in enumerate(products)}
    out = {
        "users": np.array([r["u"] for r in rows]),
        "indptr": np.cumsum([0] + [len(r["prods"]) for r in rows], dtype=np.int64),
        "prod": np.array([index[p] for r in rows for p in r["prods"]], dtype=np.uint16),
        "views": np.clip([int(v) for r in rows for v in r["views"]], 0, 65535).astype(np.uint16),
        "buys": np.clip([int(b) for r in rows for b in r["buys"]], 0, 255).astype(np.uint8),
        "carts": np.clip([int(c) for r in rows for c in r["carts"]], 0, 255).astype(np.uint8),
        "products": products,
    }
    DATA.mkdir(exist_ok=True)
    np.savez_compressed(path, **out)
    return out


def pull() -> None:
    """Rebuild every cache, one line per file."""
    for name in FEATURES:
        start = time.time()
        rows = cached(name, refresh=True)
        print(f"data/{name}.json: {len(rows)} rows, {time.time() - start:.1f}s")
    start = time.time()
    h = user_history(refresh=True)
    print(f"data/user_history.npz: {len(h['users'])} users, {len(h['prod'])} user-product pairs, {len(h['products'])} products, {time.time() - start:.1f}s")
