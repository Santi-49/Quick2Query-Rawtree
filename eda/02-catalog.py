# /// script
# requires-python = ">=3.10"
# dependencies = ["requests"]
# ///
"""Catalogue EDA: pulls shop.catalog (5,000 rows) and takes the description text apart.

    uv run eda/02-catalog.py
"""
import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from q import ROOT, query  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
rows = query("SELECT * FROM shop.catalog")
(ROOT / "data").mkdir(exist_ok=True)
(ROOT / "data" / "catalog.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
print("products", len(rows), "active", sum(r["is_active"] for r in rows))

by = lambda k: collections.Counter(r[k] for r in rows)
print("categories", len(by("category")), "subcategories", len(by("subcategory")), "brands", len(by("brand")))
brand_cats = collections.defaultdict(set)
sub_cats = collections.defaultdict(set)
for r in rows:
    brand_cats[r["brand"]].add(r["category"])
    sub_cats[r["subcategory"]].add(r["category"])
print("brands in >1 category", sum(len(v) > 1 for v in brand_cats.values()), "| subcategories in >1 category", sum(len(v) > 1 for v in sub_cats.values()))
sizes = sorted(by("subcategory").values())
print("products per subcategory min/median/max", sizes[0], sizes[len(sizes) // 2], sizes[-1])
sizes = sorted(by("brand").values())
print("products per brand min/median/max", sizes[0], sizes[len(sizes) // 2], sizes[-1])
print("created_at range", min(r["created_at"] for r in rows)[:10], max(r["created_at"] for r in rows)[:10])
print("price endings", collections.Counter(f"{r['price_eur']:.2f}"[-2:] for r in rows).most_common(4))

# Descriptions: strip brand and subcategory, see what is left.
templates = collections.Counter()
leftovers = []
for r in rows:
    d = r["description"].replace(r["brand"], "{B}").replace(r["subcategory"], "{S}")
    leftovers.append(d)
    templates[re.sub(r"[a-z][a-z' -]+", "…", d)] += 1
print("\ntemplate shapes (top 12 of", len(templates), ")")
for t, n in templates.most_common(12):
    print(f"  {n:5d}  {t}")
print("\nexamples")
for r in rows[:12]:
    print("  ", r["description"])

# Feature phrases: text between the connectors.
split = re.compile(r"\{B\}|\{S\}|\bwith\b|\band\b|\bfeaturing\b|\bComes\b|\bFrom\b|\bby\b|\bfor\b(?= \{)|[.:,()]|\ba\b|\ban\b")
phrases = collections.Counter()
per_product = []
for r, d in zip(rows, leftovers):
    found = [p.strip() for p in split.split(d) if len(p.strip()) > 3]
    per_product.append(found)
    phrases.update(found)
print("\ndistinct phrases", len(phrases), "| phrases per product", collections.Counter(len(p) for p in per_product).most_common(5))
for p, n in phrases.most_common(60):
    print(f"  {n:5d}  {p}")

# Is a phrase tied to a category, or spread across all?
cat_of = collections.defaultdict(collections.Counter)
price_of = collections.defaultdict(list)
for r, found in zip(rows, per_product):
    for p in found:
        cat_of[p][r["category"]] += 1
        price_of[p].append(r["price_eur"])
print("\nphrase · categories it appears in · share in its top category · median price")
for p, n in phrases.most_common(40):
    c = cat_of[p]
    prices = sorted(price_of[p])
    print(f"  {p:32s} {len(c):2d}  {max(c.values()) / n:.2f}  {prices[len(prices) // 2]:7.2f}")
