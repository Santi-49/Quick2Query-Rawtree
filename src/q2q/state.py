"""The live state read by strategies: catalogue, stock, appeal, shopper memory, trend, segment lift.

Thread rule: refresh() runs in a router thread while strategies read. Published lists and dicts are
replaced by new objects in one assignment, never mutated in place (live purchase sets excepted).
"""
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np

from q2q import data, rt

FEATURES = ["sporty style", "family-size format", "luxury feel", "minimalist design", "compact and lightweight", "vintage look", "travel-ready build", "waterproof shell",
            "designed for kids", "handmade finish", "premium materials", "wireless connectivity", "organic ingredients", "built for professionals", "bold colours",
            "whisper-quiet operation", "smart app control", "recycled materials", "great value for money", "extra durability"]
BACK_DELAY = 60.0       # seconds before a back_in_stock product may be shown
PRIOR = 50.0            # pseudo-views of the attribute prior in buys per view
NEW_BOOST = 1.2
EVERY = {"updates": 1.0, "purchases": 5.0, "today": 5.0, "trend": 30.0}
TODAY_KEEP = 10         # products viewed today kept per shopper

UPDATE_COLS = """toString(ts::DateTime64(3)) AS ts, product_id::String AS product_id, change::String AS change, category::String AS category,
       subcategory::String AS subcategory, brand::String AS brand, price_eur::Float64 AS price_eur, description::String AS description, is_active::Bool AS is_active"""
EVENT_BUYS = """SELECT user_id::String AS u, product_id::String AS p, toString(ts::DateTime64(3)) AS ts FROM shop.events
WHERE event_type::String = 'purchase' {since}"""
FEEDBACK_BUYS = """SELECT r.u AS u, f.p AS p, f.ts AS ts
FROM (SELECT request_id::String AS id, purchased::String AS p, toString(ts::DateTime64(3)) AS ts FROM {TEAM}.feedback
      WHERE purchased::String != '' {since}) AS f
INNER JOIN (SELECT request_id::String AS id, user_id::String AS u FROM shop.requests) AS r ON f.id = r.id"""
TODAY = """SELECT user_id::String AS u, product_id::String AS p, event_type::String AS et, toString(ts::DateTime64(3)) AS ts FROM shop.events
WHERE event_type::String IN ('view', 'add_to_cart') AND {where} ORDER BY ts::DateTime64(3)"""
TREND = """WITH (SELECT max(ts::DateTime64(3)) FROM shop.events) AS now
SELECT product_id::String AS p, countIf(t > now - INTERVAL 15 MINUTE) AS v15, count() AS v120
FROM (SELECT product_id, ts::DateTime64(3) AS t FROM shop.events WHERE event_type::String = 'view')
WHERE t > now - INTERVAL 120 MINUTE GROUP BY p"""


@dataclass(slots=True)
class Product:
    id: str
    category: str
    subcategory: str
    brand: str
    price: float
    phrases: tuple[str, ...]
    is_new: bool        # arrived through a new_product update
    views: int          # history organic counts (0 for new products)
    buys: int
    appeal: float


@dataclass(slots=True)
class Shopper:
    bought: set[str]              # history purchases + live purchases
    viewed: dict[str, int]        # product -> history view count, only products not bought
    cat_share: dict[str, float]   # category -> share of the shopper's history views
    carted: dict[str, int] = field(default_factory=dict)  # product -> times added to the cart (history + today), only products not bought


def epoch(ts: str) -> float:
    """'2026-11-14 13:15:00.000' (UTC) -> epoch seconds."""
    return datetime.fromisoformat(ts).replace(tzinfo=timezone.utc).timestamp()


def phrases(description: str) -> tuple[str, ...]:
    return tuple(f for f in FEATURES if f in description)


def appeal(v: float, b: float, pred_b: float) -> float:
    """Popularity times shrunk buys per view."""
    bpv = (b + PRIOR * math.exp(pred_b)) / (v + PRIOR)
    return (v + 1) ** 0.2 * bpv ** 0.5


def new_appeal(pred_a: float, pred_b: float) -> float:
    """Appeal of a product without history: predicted views, predicted buys per view, boosted."""
    return (math.exp(pred_a) + 1) ** 0.2 * math.exp(pred_b) ** 0.5 * NEW_BOOST


def trend_from(rows: list[dict], sub_of: dict[str, str]) -> dict[str, float] | None:
    """Subcategory multipliers from per-product view counts of the last 15 and 120 minutes; None if too few views."""
    v15, v120 = {}, {}
    for r in rows:
        sub = sub_of.get(r["p"])
        if sub is not None:
            v15[sub] = v15.get(sub, 0) + int(r["v15"])
            v120[sub] = v120.get(sub, 0) + int(r["v120"])
    t15, t120 = sum(v15.values()), sum(v120.values())
    if t15 < 500:
        return None
    out = {}
    for sub, n in v120.items():
        if n > 0:
            s120 = n / t120
            out[sub] = min(3.0, max(0.7, (v15[sub] + 20 * s120) / (t15 + 20) / s120))
    return out


def segment_from(rows: list[dict]) -> dict[tuple[str, str], dict[str, float]]:
    """(device, region) -> category -> purchase lift over the category's overall rate, shrunk and clipped."""
    req, buy = {}, {}
    for r in rows:
        req[r["category"]] = req.get(r["category"], 0) + int(r["requests"])
        buy[r["category"]] = buy.get(r["category"], 0) + int(r["buys"])
    out = {}
    for r in rows:
        rate = buy[r["category"]] / req[r["category"]]
        lift = (int(r["buys"]) + 5) / (int(r["requests"]) * rate + 5)
        out.setdefault((r["device"], r["region"]), {})[r["category"]] = min(15.0, max(0.3, lift))
    return out


class State:
    def __init__(self):
        self.products: dict[str, Product] = {}
        self.best: list[str] = []
        self.by_appeal: list[str] = []
        self.by_subcategory: dict[str, list[str]] = {}
        self.by_category: dict[str, list[str]] = {}
        self.new_products: list[str] = []
        self.trend: dict[str, float] = {}
        self.price_cut: dict[str, float] = {}
        self.segment: dict[tuple[str, str], dict[str, float]] = {}
        self._base_price: dict[str, float] = {}
        self._inactive: set[str] = set()
        self._until: dict[str, float] = {}      # product -> epoch from which it may be shown (inf: out of stock)
        self._applied: set[tuple] = set()       # (ts, product_id, change) of update rows applied
        self._last_update = "1970-01-01 00:00:00.000"
        self._model = ({}, np.zeros(1), np.zeros(1))  # column index, coefficients for log views and log buys per view
        self._hist: dict = {}
        self._user_row: dict[str, int] = {}
        self._hist_products: list[str] = []
        self._live: dict[str, set[str]] = {}
        self._last_buy = {"events": "", "feedback": ""}
        self._today: dict[str, list[str]] = {}          # user -> last products viewed today, newest last
        self._today_carts: dict[str, dict[str, int]] = {}
        self._seen_today: set[tuple] = set()            # (u, p, et, ts) of the overlap window
        self._last_today = ""
        self._next = {k: 0.0 for k in EVERY}

    # ---------- load ----------

    def load(self) -> None:
        start = t = time.time()

        def lap(what):
            nonlocal t
            print(f"state: {what} {time.time() - t:.1f}s")
            t = time.time()

        stats = {r["p"]: (int(r["views"]), int(r["buys"])) for r in data.cached("product_stats")}
        catalog = rt.query("""SELECT product_id::String AS id, category::String AS category, subcategory::String AS subcategory, brand::String AS brand,
                                     price_eur::Float64 AS price, description::String AS description, is_active::Bool AS active FROM shop.catalog""")
        lap(f"catalogue {len(catalog)} products")
        products = {}
        for r in catalog:
            v, b = stats.get(r["id"], (0, 0))
            products[r["id"]] = Product(r["id"], r["category"], r["subcategory"], r["brand"], r["price"], phrases(r["description"]), False, v, b, 0.0)
            self._base_price[r["id"]] = r["price"]
            if not r["active"]:
                self._inactive.add(r["id"])
        self._fit(products)
        for p in products.values():
            p.appeal = appeal(p.views, p.buys, self._predict(p)[1])
        self.products = products
        self.best = [pid for _, pid in sorted(((p.buys, p.id) for p in products.values() if p.buys > 0), reverse=True)]
        lap("appeal model")

        rows = rt.query(f"SELECT {UPDATE_COLS} FROM shop.catalog_updates ORDER BY ts::DateTime64(3)")
        for r in rows:
            self._apply(r, epoch(r["ts"]))
        self._index()
        lap(f"catalogue updates {len(rows)} rows")

        self._hist = data.user_history()
        self._user_row = {u: i for i, u in enumerate(self._hist["users"].tolist())}
        self._hist_products = self._hist["products"].tolist()
        lap(f"user history {len(self._user_row)} users")

        self._purchases()
        lap(f"live purchases {sum(map(len, self._live.values()))} for {len(self._live)} users")
        self._today_events()
        lap(f"today's views for {len(self._today)} users")
        self._trend()
        lap(f"trend {len(self.trend)} subcategories")
        self.segment = segment_from(data.cached("segment_category"))
        lap(f"segment lift {len(self.segment)} segments")
        now = time.time()
        self._next = {k: now + s for k, s in EVERY.items()}
        print(f"state: loaded in {time.time() - start:.1f}s")

    def _fit(self, products: dict[str, Product]) -> None:
        """Least squares of log views and log buys per view on subcategory, brand and phrases (products with >= 200 views)."""
        train = [p for p in products.values() if p.views >= 200]
        names = sorted({"s:" + p.subcategory for p in train} | {"b:" + p.brand for p in train}) + ["f:" + f for f in FEATURES]
        cols = {n: i + 1 for i, n in enumerate(names)}
        self._model = (cols, None, None)
        X = np.array([self._x(p) for p in train])
        v = np.array([p.views for p in train], dtype=float)
        b = np.array([p.buys for p in train], dtype=float)
        beta_a = np.linalg.lstsq(X, np.log(v), rcond=None)[0]
        beta_b = np.linalg.lstsq(X, np.log((b + 1) / (v + 50)), rcond=None)[0]
        self._model = (cols, beta_a, beta_b)

    def _x(self, p: Product) -> np.ndarray:
        cols = self._model[0]
        x = np.zeros(len(cols) + 1)
        x[0] = 1.0
        for name in ["s:" + p.subcategory, "b:" + p.brand] + ["f:" + f for f in p.phrases]:
            if name in cols:
                x[cols[name]] = 1.0
        return x

    def _predict(self, p: Product) -> tuple[float, float]:
        """(predicted log views, predicted log buys per view)."""
        x = self._x(p)
        return float(x @ self._model[1]), float(x @ self._model[2])

    # ---------- catalogue updates ----------

    def _apply(self, r: dict, seen_at: float) -> bool:
        """Apply one catalog_updates row once; True if it was new. Call _index() after a new_product."""
        key = (r["ts"], r["product_id"], r["change"])
        if key in self._applied:
            return False
        self._applied.add(key)
        self._last_update = max(self._last_update, r["ts"])
        pid, change = r["product_id"], r["change"]
        if change == "new_product":
            p = Product(pid, r["category"], r["subcategory"], r["brand"], r["price_eur"], phrases(r["description"]), True, 0, 0, 0.0)
            p.appeal = new_appeal(*self._predict(p))
            self._base_price[pid] = p.price
            if not r["is_active"]:
                self._inactive.add(pid)
            self.products = {**self.products, pid: p}
            if pid not in self.new_products:
                self.new_products = self.new_products + [pid]
        elif pid not in self.products:
            return True
        elif change == "out_of_stock":
            self._until[pid] = math.inf
        elif change == "back_in_stock":
            self._until[pid] = max(epoch(r["ts"]), seen_at) + BACK_DELAY
        elif change == "price_change":
            self.products[pid].price = r["price_eur"]
            ratio = r["price_eur"] / self._base_price[pid]
            cuts = {k: v for k, v in self.price_cut.items() if k != pid}
            if ratio < 1:
                cuts[pid] = ratio
            self.price_cut = cuts
        return True

    def _index(self) -> None:
        """Rebuild the appeal-sorted lists."""
        ranked = sorted(self.products.values(), key=lambda p: -p.appeal)
        by_sub, by_cat = {}, {}
        for p in ranked:
            by_sub.setdefault(p.subcategory, []).append(p.id)
            by_cat.setdefault(p.category, []).append(p.id)
        self.by_appeal = [p.id for p in ranked]
        self.by_subcategory = by_sub
        self.by_category = by_cat

    def _updates(self) -> None:
        now = time.time()
        rows = rt.query(f"SELECT {UPDATE_COLS} FROM shop.catalog_updates WHERE ts::DateTime64(3) >= toDateTime64('{self._last_update}', 3) ORDER BY ts::DateTime64(3)")
        new = [r for r in rows if self._apply(r, now)]
        if any(r["change"] == "new_product" for r in new):
            self._index()

    # ---------- live purchases, trend ----------

    def _purchases(self) -> None:
        for source, sql in (("events", EVENT_BUYS), ("feedback", FEEDBACK_BUYS)):
            last = self._last_buy[source]
            since = f"AND ts::DateTime64(3) > toDateTime64('{last}', 3) - INTERVAL 3 SECOND" if last else ""
            for r in rt.query(sql.replace("{since}", since)):
                self._live.setdefault(r["u"], set()).add(r["p"])
                last = max(last, r["ts"])
            self._last_buy[source] = last

    def _today_events(self) -> None:
        """Views and carts of shop.events: the last 2 hours at start, then what is new."""
        if self._last_today:
            chunks = [f"ts::DateTime64(3) > toDateTime64('{self._last_today}', 3) - INTERVAL 3 SECOND"]
        else:
            chunks = [f"ts::DateTime64(3) > (SELECT max(ts::DateTime64(3)) FROM shop.events) - INTERVAL 120 MINUTE AND cityHash64(user_id::String) % 4 = {c}" for c in range(4)]
        rows = sorted((r for where in chunks for r in rt.query(TODAY.replace("{where}", where))), key=lambda r: r["ts"])
        seen = set()
        for r in rows:
            key = (r["u"], r["p"], r["et"], r["ts"])
            seen.add(key)
            if key in self._seen_today:
                continue
            if r["et"] == "view":
                self._today[r["u"]] = ([p for p in self._today.get(r["u"], ()) if p != r["p"]] + [r["p"]])[-TODAY_KEEP:]
            else:
                carts = dict(self._today_carts.get(r["u"], ()))
                carts[r["p"]] = carts.get(r["p"], 0) + 1
                self._today_carts[r["u"]] = carts
        if rows:
            self._last_today = rows[-1]["ts"]
            last = epoch(self._last_today)
            self._seen_today = {k for k in seen if epoch(k[3]) > last - 3}

    def _trend(self) -> None:
        trend = trend_from(rt.query(TREND), {pid: p.subcategory for pid, p in self.products.items()})
        if trend is not None:
            self.trend = trend

    # ---------- public ----------

    def refresh(self) -> None:
        """Run the steps that are due; each step fails alone and keeps the previous state."""
        for step, fn in (("updates", self._updates), ("purchases", self._purchases), ("today", self._today_events), ("trend", self._trend)):
            now = time.time()
            if now < self._next[step]:
                continue
            self._next[step] = now + EVERY[step]
            try:
                fn()
            except Exception as e:
                print(f"state: {step} failed: {str(e)[:200]}")

    def available(self, pid: str) -> bool:
        return pid in self.products and pid not in self._inactive and time.time() >= self._until.get(pid, 0.0)

    def today_views(self, user_id: str) -> list[str]:
        """Products the shopper viewed earlier today (organic events), newest last."""
        return self._today.get(user_id, [])

    def shopper(self, user_id: str, live: bool = True) -> Shopper | None:
        """What we know about a shopper. live=False leaves out today, for training on past feedback without leaking its outcome."""
        i = self._user_row.get(user_id)
        carted = dict(self._today_carts.get(user_id, ())) if live else {}
        live = self._live.get(user_id, set()) if live else set()
        if i is None and not live and not carted:
            return None
        bought, viewed, cat_views = set(live), {}, {}
        carts = self._hist.get("carts")
        if i is not None:
            lo, hi = self._hist["indptr"][i], self._hist["indptr"][i + 1]
            for k, v, b, c in zip(self._hist["prod"][lo:hi].tolist(), self._hist["views"][lo:hi].tolist(), self._hist["buys"][lo:hi].tolist(),
                                  carts[lo:hi].tolist() if carts is not None else [0] * (hi - lo)):
                pid = self._hist_products[k]
                if c:
                    carted[pid] = carted.get(pid, 0) + c
                if b:
                    bought.add(pid)
                elif v and pid not in live:
                    viewed[pid] = v
                p = self.products.get(pid)
                if v and p is not None:
                    cat_views[p.category] = cat_views.get(p.category, 0) + v
        total = sum(cat_views.values())
        return Shopper(bought, viewed, {c: n / total for c, n in cat_views.items()} if total else {}, {p: n for p, n in carted.items() if p not in bought})
