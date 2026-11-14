# /// script
# requires-python = ">=3.10"
# dependencies = ["requests", "numpy"]
# ///
"""How much of a product's popularity and buy rate do its attributes explain? (cold-start question)

    uv run eda/08-product-appeal.py

Pulls one row per product (organic views, carts, purchases) and joins the catalogue copy in data/catalog.json.
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from q import ROOT, query  # noqa: E402

FEATURES = ["sporty style", "family-size format", "luxury feel", "minimalist design", "compact and lightweight", "vintage look", "travel-ready build", "waterproof shell",
            "designed for kids", "handmade finish", "premium materials", "wireless connectivity", "organic ingredients", "built for professionals", "bold colours",
            "whisper-quiet operation", "smart app control", "recycled materials", "great value for money", "extra durability"]

catalog = {p["product_id"]: p for p in json.loads((ROOT / "data" / "catalog.json").read_text(encoding="utf-8"))}
rows = query("""SELECT product_id::String AS p, countIf(event_type::String = 'view') AS views, countIf(event_type::String = 'add_to_cart') AS carts,
                       countIf(event_type::String = 'purchase') AS buys, uniqExact(user_id::String) AS users FROM shop.history_events GROUP BY p""")
for r in rows:
    r.update(catalog[r["p"]])
    r["feats"] = [f for f in FEATURES if f in r["description"]]
    r["template"] = re.sub(r"[A-Z].*", "", r["description"])[:8] or r["description"].split()[0]

print(f"products {len(rows)}, features per product: {np.bincount([len(r['feats']) for r in rows]).tolist()}")


def table(key, label, top=None):
    groups = defaultdict(list)
    for r in rows:
        for k in (r[key] if isinstance(r[key], list) else [r[key]]):
            groups[k].append(r)
    out = []
    for k, g in groups.items():
        views = sum(x["views"] for x in g)
        out.append((k, len(g), views / len(g), 100 * sum(x["carts"] for x in g) / views, 100 * sum(x["buys"] for x in g) / views, float(np.median([x["price_eur"] for x in g]))))
    out.sort(key=lambda x: -x[4])
    print(f"\n{label}: group, products, views per product, cart per view %, buy per view %, median price")
    for row in (out if top is None else out[:top] + [("...",) * 1] + out[-top:]):
        print("  " + " | ".join(f"{v:.2f}" if isinstance(v, float) else str(v) for v in row))


table("feats", "by description feature")
table("category", "by category")
table("subcategory", "by subcategory (top and bottom 6)", top=6)
table("brand", "by brand (top and bottom 6)", top=6)

# variance of log views and of buy-per-view explained by attribute groups (one-hot least squares, in-sample R2)
y_views = np.log([max(r["views"], 1) for r in rows])
y_buy = np.array([r["buys"] / max(r["views"], 1) for r in rows])
log_price = np.log([r["price_eur"] for r in rows])
age = np.array([r["created_at"][:10] for r in rows])


def onehot(values):
    keys = sorted(set(values))
    return np.array([[v == k for k in keys] for v in values], dtype=float)


def r2(blocks, y):
    X = np.hstack([np.ones((len(rows), 1))] + blocks)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    return 1 - ((y - X @ beta) ** 2).sum() / ((y - y.mean()) ** 2).sum()


blocks = {
    "category": onehot([r["category"] for r in rows]),
    "subcategory": onehot([r["subcategory"] for r in rows]),
    "brand": onehot([r["brand"] for r in rows]),
    "features": np.array([[f in r["feats"] for f in FEATURES] for r in rows], dtype=float),
    "price": np.column_stack([log_price, log_price ** 2]),
}
print("\nR2 (in-sample) of attribute groups: log(views), buy per view")
for name, b in blocks.items():
    print(f"  {name}: {r2([b], y_views):.3f}, {r2([b], y_buy):.3f}")
print(f"  subcategory + brand + features + price: {r2([blocks['subcategory'], blocks['brand'], blocks['features'], blocks['price']], y_views):.3f}, "
      f"{r2([blocks['subcategory'], blocks['brand'], blocks['features'], blocks['price']], y_buy):.3f}")
print("\nviews per product: quantiles 5/25/50/75/95:", np.percentile([r["views"] for r in rows], [5, 25, 50, 75, 95]).round().tolist())
print("buy per view %: quantiles 5/25/50/75/95:", (100 * np.percentile(y_buy, [5, 25, 50, 75, 95])).round(2).tolist())
print("corr(log price, buy per view):", round(float(np.corrcoef(log_price, y_buy)[0, 1]), 3), "| corr(log price, log views):", round(float(np.corrcoef(log_price, y_views)[0, 1]), 3))
newest = sorted(rows, key=lambda r: r["created_at"])[-250:]
print("newest 250 products vs all, views per product:", round(float(np.mean([r["views"] for r in newest]))), "vs", round(float(np.mean([r["views"] for r in rows]))))
