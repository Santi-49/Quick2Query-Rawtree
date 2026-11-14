"""Product embeddings: truncated SVD of the PPMI matrix of products touched by one shopper on one day.

    uv run python -m q2q.emb                              # 30 days of history + today's events so far -> data/emb/
    uv run python -m q2q.emb "2026-11-14 15:00:00" DIR    # today's events before a cut, into DIR (holdout)

Pairs come from sql/features/emb_pairs.sql in 16 hash chunks. Writes products.npy (float32, rows L2-normalised) and
products.json (the product ids, same order). Serving needs only these two files (numpy, no scipy).
"""
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import svds

from q2q import data, rt

DIR = rt.ROOT / "data" / "emb"
DIMS, PRODUCTS, ALPHA = 32, 5000, 0.75


def pairs(until: str) -> list[dict]:
    text = data.sql("emb_pairs").replace("{until}", until)
    with ThreadPoolExecutor(4) as pool:
        return [r for part in pool.map(lambda c: rt.query(text.replace("{chunk}", str(c)), timeout=60), range(16)) for r in part]


def embed(rows: list[dict]) -> tuple[list[str], np.ndarray]:
    weight = {}
    for r in rows:
        weight[r["a"]] = sum(map(int, r["ns"]))
    ids = sorted(weight, key=weight.get, reverse=True)[:PRODUCTS]
    index = {p: i for i, p in enumerate(ids)}
    a, b, n = [], [], []
    for r in rows:
        i = index.get(r["a"])
        if i is None:
            continue
        for q, k in zip(r["bs"], r["ns"]):
            j = index.get(q)
            if j is not None:
                a.append(i), b.append(j), n.append(float(k))
    c = coo_matrix((n, (a, b)), shape=(len(ids), len(ids))).tocsr()
    total, row = c.sum(), np.asarray(c.sum(1)).ravel()
    ctx = row ** ALPHA
    ctx /= ctx.sum()
    c = c.tocoo()
    pmi = np.log(c.data / total / (row[c.row] / total) / ctx[c.col])
    keep = pmi > 0
    m = coo_matrix((pmi[keep], (c.row[keep], c.col[keep])), shape=c.shape).tocsr()
    u, s, _ = svds(m, k=DIMS)
    e = (u * np.sqrt(s)).astype(np.float32)
    e /= np.maximum(np.linalg.norm(e, axis=1, keepdims=True), 1e-9)
    return ids, e


def build(until: str | None = None, out=DIR) -> None:
    start = time.time()
    until = until or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    rows = pairs(until)
    print(f"{sum(len(r['bs']) for r in rows):,} pairs from {len(rows):,} products (events before {until} UTC) in {time.time() - start:.0f} s", flush=True)
    ids, e = embed(rows)
    out.mkdir(parents=True, exist_ok=True)
    np.save(out / "products.npy", e)
    (out / "products.json").write_text(json.dumps(ids), encoding="utf-8")
    print(f"saved {e.shape} to {out} in {time.time() - start:.0f} s", flush=True)


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else None, rt.ROOT / sys.argv[2] if len(sys.argv) > 2 else DIR)
