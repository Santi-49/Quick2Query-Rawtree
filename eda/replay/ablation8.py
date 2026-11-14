"""Ablation of ranker3's input groups, ranker2's post-model multipliers and rules5's components, in leak-free replay.

    uv run eda/replay/ablation8.py table      # train8.table on all feedback -> data/replay/abl/table.npz (ranker8.ALL columns)
    uv run eda/replay/ablation8.py ablate     # per cut: fit every variant on rows before the window, replay the window
    uv run eda/replay/ablation8.py rules5     # per cut: rules5 with one component neutral at a time
    uv run eda/replay/ablation8.py report     # paired differences against the full model, pooled over the cuts

Cuts: 2-hour windows starting 13:00, 15:00, 17:00 UTC (the test window of ranker8, 19:00 to now, is not used here).
Every row of the table is built from data strictly before its request, so a cut is a slice t < window start.
Click models: all clicks and a random 30% of non-clicked impressions (weight 1 / 0.3), the same rows for every variant
of a cut; buy-given-click models on every click. Replay: requests with a purchase, State as of each request as in
holdout3 (cart times and our earlier clicks included). Models and indicators go to data/replay/abl/, never models/.
"""
import importlib.util
import sys
import time
from bisect import bisect_left
from contextlib import contextmanager

import lightgbm as lgb
import numpy as np
import pandas as pd

from q2q import replay, rt, train8
from q2q.state import State, epoch
from q2q.strategies import ranker3, ranker8, rules5
from q2q.strategy import Request, guard
from q2q.train import PARAMS

DIR = rt.ROOT / "data" / "replay" / "abl"
DAY = "2026-11-14"
CUTS = [("13:00:00", "15:00:00"), ("15:00:00", "17:00:00"), ("17:00:00", "19:00:00")]
NEG = 0.3
ALL = ranker8.ALL
GROUPS = {
    "slot": ["slot"],
    "product appeal/conversion": ["appeal", "log_views", "log_buys", "is_new_product", "log_appeal", "log_bpv"],
    "price": ["price"],
    "session relation": ["is_last_view", "in_views", "views_ago", "same_sub_last", "same_cat_last", "same_sub_any", "same_cat_any",
                         "is_first_view", "is_later_view", "in_main_cat"],
    "session shape": ["n_views", "single_view_session", "n_recent_views"],
    "shopper history shares": ["viewed_before", "cat_share", "known_shopper", "brand_share", "sub_share", "cat_carts"],
    "phrase taste": ["phrase_share", "session_phrase_overlap"],
    "history carts, cart rate": ["carted_not_bought", "shopper_cart_rate", "cart_x_high_cart_rate"],
    "co-views": ["coview"],
    "today's views": ["viewed_today", "sub_viewed_today"],
    "today's carts": ["carted_today", "mins_since_cart_today", "cat_carted_today", "sub_carted_today"],
    "cart time today": ["mins_since_cart_today"],
    "own-list clicks": ["clicked_ours_today"],
    "context (segment, page, device, new)": ["segment", "page", "device", "new_shopper"],
}
BASE = [f for f in ranker3.FEATURES]  # the full model: ranker3's inputs
VARIANTS = {"full": BASE, **{f"-{g}": [f for f in BASE if f not in fs] for g, fs in GROUPS.items()}, "+rules5_rank": BASE + ["rules5_rank"]}
CLICKS = """SELECT r.u AS u, f.p AS p, f.q AS q, f.t AS t FROM
    (SELECT request_id::String AS rid, any(clicked::String) AS p, any(purchased::String) AS q, any(toUnixTimestamp64Milli(ts::DateTime64(3, 'UTC')) / 1000) AS t
     FROM {TEAM}.feedback WHERE clicked::String != '' GROUP BY rid) f
    INNER JOIN (SELECT request_id::String AS rid, any(user_id::String) AS u FROM shop.requests GROUP BY rid) r ON r.rid = f.rid"""


def pull_window(start: str, end: str) -> dict:
    """replay's four frames for [start, end), cached under DIR."""
    tag = f"{start[11:13]}{start[14:16]}_{end[11:13]}{end[14:16]}"
    paths = {k: DIR / f"{k}_{tag}.parquet" for k in ("reqs", "buys", "today", "meta")}
    if all(p.exists() for p in paths.values()):
        return {k: pd.read_parquet(p) for k, p in paths.items()}
    spec = importlib.util.spec_from_file_location("replay_pull", rt.ROOT / "eda" / "replay" / "pull.py")
    pull = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pull)
    reqs = pull.run("reqs", start, end).sort_values("t", ignore_index=True)
    buys = pd.concat([pull.run("events", start, end).assign(organic=True), pull.run("fed", start, end).assign(organic=False)], ignore_index=True)
    out = {"reqs": reqs, "buys": buys.sort_values("t", ignore_index=True), "today": pull.run("today", start, end).sort_values("t", ignore_index=True),
           "meta": pd.DataFrame([{"start": start, "end": end}])}
    DIR.mkdir(parents=True, exist_ok=True)
    for k, df in out.items():
        df.to_parquet(paths[k])
    print(f"pulled {start} to {end}: {len(reqs):,} requests, {(reqs['purchased'] != '').sum()} purchases", flush=True)
    return out


def purchases(frames):
    """Requests with a purchase, with route, logger and the State inputs replay rebuilds."""
    reqs, shares, buys, today = replay.prepare(frames, 0, 0)
    return reqs[reqs["purchased"] != ""].reset_index(drop=True), buys, today


def our_clicks() -> dict:
    out = {}
    for r in sorted(rt.query(CLICKS, timeout=60), key=lambda r: float(r["t"])):
        ts, ps, qs = out.setdefault(r["u"], ([], [], []))
        ts.append(float(r["t"]))
        ps.append(r["p"])
        qs.append(r["q"])
    return out


def as_of(state, u, t, buys, today, clicks):
    """replay.as_of plus cart times and our clicks today, as holdout3."""
    replay.as_of(state, u, t, buys, today)
    ts, ps, carts = today.get(u, ((), [], []))
    k = bisect_left(ts, t)
    state._cart_last[u] = {p: tt for tt, p, c in zip(ts[:k], ps[:k], carts[:k]) if c}
    ts, ps, qs = clicks.get(u, ((), [], []))
    j = bisect_left(ts, t)
    state.our_clicks_today[u] = {p for p, q in zip(ps[:j], qs[:j]) if p != q}


def new_state():
    state = State()
    state.load()
    state._until = {}  # stock ignored, as replay.run
    state.our_clicks_today, state._cart_last = {}, {}
    state.today_cart_last = lambda user: state._cart_last.get(user, {})
    return state


def carted_today(reqs, today) -> np.ndarray:
    out = []
    for u, t, q in zip(reqs["u"], reqs["t"], reqs["purchased"]):
        ts, ps, cs = today.get(u, ((), [], []))
        out.append(q in {p for p, c in zip(ps[:bisect_left(ts, t)], cs) if c})
    return np.array(out)


def hits(reqs, tops, name) -> pd.DataFrame:
    ind = replay.indicators(name, reqs, tops)[["route", "hit1", "hit3", "hit10"]]
    return ind


def fit_variants(X, y, b, t, cut_ms, names):
    old = t < cut_ms
    rng = np.random.default_rng(0)
    keep = old & ((y == 1) | (rng.random(len(y)) < NEG))
    w = np.where(y[keep] == 1, 1.0, 1 / NEG)
    params = {**PARAMS, "num_threads": 4}
    clicked = old & (y == 1)
    small = clicked.sum() < 1500
    buy_params = {**params, "num_leaves": 7, "min_data_in_leaf": 50} if small else params
    print(f"  rows before cut {old.sum():,} ({keep.sum():,} kept for click models), clicks {clicked.sum():,}, purchases {b[clicked].sum()}", flush=True)
    models = {}
    for name in names:
        cols = [ALL.index(f) for f in VARIANTS[name]]
        s = time.time()
        click = lgb.train(params, lgb.Dataset(X[keep][:, cols], y[keep], weight=w), num_boost_round=300)
        buy = lgb.train(buy_params, lgb.Dataset(X[clicked][:, cols], b[clicked]), num_boost_round=100 if small else 300)
        models[name] = (click, buy, cols)
        print(f"  fitted {name} in {time.time() - s:.0f} s", flush=True)
    return models


def replay_models(reqs, state, buys, today, clicks, models, plain: bool = False) -> dict[str, list]:
    """Top 10 per variant, plus the full model's multiplier variants and rules5, from one feature matrix per request.
    plain: as ranker8 serves (rules5's top 10 added to the candidates, score = click x buy, no multiplier)."""
    out = {n: [] for n in list(models) + ["full: no trend", "full: no price cut", "full: click only", "full: buy only", "rules5"]}
    for r in reqs.itertuples(index=False):
        as_of(state, r.u, r.t, buys, today, clicks)
        req = Request(r.rid, r.t, r.u, bool(r.new), r.page, r.dev, r.reg, list(r.vp))
        c = ranker3.context(req, state)
        r5 = ranker8.rules5_ranks(req, state)
        out["rules5"].append(guard(list(r5), state))
        cands = ranker3.candidates(state, c)
        if plain:
            have = {p.id for p in cands}
            cands += [state.products[p] for p in r5 if p not in have and p not in c["bought"] and p in state.products]
        if not cands:
            for n in out:
                if n != "rules5":
                    out[n].append(guard([], state))
            continue
        ids = [p.id for p in cands]
        X = np.array([ranker8.full_row(p, req, c, r5) for p in cands], dtype=float)
        trend = np.array([1.0 if plain else state.trend.get(p.subcategory, 1.0) for p in cands])
        cut = np.array([1.0 if plain else 2 - state.price_cut.get(p.id, 1.0) for p in cands])

        def top(score):
            return guard([ids[i] for i in np.argsort(-score, kind="stable")[:10]], state)
        for n, (click, buy, cols) in models.items():
            k, q = click.predict(X[:, cols]), buy.predict(X[:, cols])
            out[n].append(top(k * q * trend * cut))
            if n == "full":
                out["full: no trend"].append(top(k * q * cut))
                out["full: no price cut"].append(top(k * q * trend))
                out["full: click only"].append(top(k * trend * cut))
                out["full: buy only"].append(top(q * trend * cut))
    return out


def select() -> None:
    """ranker8's feature set, with train2's and train8's parameters, against ranker3's inputs + rules5_rank; all rows, no subsampling."""
    d = np.load(DIR / "table.npz")
    X, y, b, t = d["X"], d["y"], d["b"], d["t"]
    state, clicks = new_state(), our_clicks()
    full = [ALL.index(f) for f in BASE + ["rules5_rank"]]
    for start, end in CUTS:
        frames = pull_window(f"{DAY} {start}", f"{DAY} {end}")
        reqs, buys, today = purchases(frames)
        old = t < epoch(f"{DAY} {start}") * 1000
        Xo, yo, bo = X[old], y[old], b[old]
        small = yo.sum() < 1500
        buy_params = {**PARAMS, "num_leaves": 7, "min_data_in_leaf": 50} if small else PARAMS
        models = {}
        for name, cols in (("full +rules5_rank", full), ("ranker8 set", ranker8.COLS)):
            models[name] = (lgb.train(PARAMS, lgb.Dataset(Xo[:, cols], yo), num_boost_round=300),
                            lgb.train(buy_params, lgb.Dataset(Xo[yo == 1][:, cols], bo[yo == 1]), num_boost_round=100 if small else 300), cols)
        models["ranker8 set, PARAMS8"] = (*train8.fit(Xo[:, ranker8.COLS], yo, bo), ranker8.COLS)
        tops = replay_models(reqs, state, buys, today, clicks, models, plain=True)
        print(f"cut {start}: {len(reqs)} purchase requests", flush=True)
        save(reqs, today, {n: tops[n] for n in list(models) + ["rules5"]}, f"select_{start[:2]}")


def ablate() -> None:
    d = np.load(DIR / "table.npz")
    X, y, b, t = d["X"], d["y"], d["b"], d["t"]
    state, clicks = new_state(), our_clicks()
    for start, end in CUTS:
        frames = pull_window(f"{DAY} {start}", f"{DAY} {end}")
        reqs, buys, today = purchases(frames)
        print(f"cut {start}: {len(reqs)} purchase requests", flush=True)
        models = fit_variants(X, y, b, t, epoch(f"{DAY} {start}") * 1000, list(VARIANTS))
        s = time.time()
        tops = replay_models(reqs, state, buys, today, clicks, models)
        print(f"  replayed in {time.time() - s:.0f} s", flush=True)
        save(reqs, today, tops, f"ablate_{start[:2]}")


def save(reqs, today, tops, tag):
    frames = []
    tc = carted_today(reqs, today)
    for n, lists in tops.items():
        ind = hits(reqs, lists, n)
        ind["variant"], ind["rid"], ind["carted_today"] = n, reqs["rid"].to_numpy(), tc
        frames.append(ind)
    pd.concat(frames, ignore_index=True).to_parquet(DIR / f"{tag}.parquet")


@contextmanager
def patched(pairs):
    """Set (object, attribute, value) for the block, then restore."""
    old = [(obj, attr, getattr(obj, attr)) for obj, attr, _ in pairs]
    for obj, attr, value in pairs:
        setattr(obj, attr, value)
    try:
        yield
    finally:
        for obj, attr, value in old:
            setattr(obj, attr, value)


def r5_variants(state) -> dict[str, list]:
    """rules5 component -> the patches that make it neutral."""
    return {
        "rules5": [],
        "today carts x30 (-> 1)": [(rules5, "TODAY_CART", 1.0)],
        "only view x18 (-> first view 12)": [(rules5, "ONLY_VIEW", 12.0)],
        "last view x3 (-> other view 5)": [(rules5, "LAST_VIEW", 5.0)],
        "history cart count (-> 1)": [(rules5, "CART_COUNT", (1.0, 1.0, 1.0))],
        "history cart views (-> 1)": [(rules5, "CART_VIEWS", (1.0, 1.0, 1.0))],
        "conversion bpv (-> 1)": [(rules5, "conversion", lambda p: 1.0)],
        "home flatter cart base (-> cold2)": [(rules5, "home", lambda req, s: rules5.COLD2.explain(req, s))],
        "history cart x6 (-> 1)": [(rules5, "CARTED", 1.0)],
        "session and past x1.4 (-> 1)": [(rules5, "BOTH", 1.0)],
        "favourite category share (-> 0)": [(rules5, "SHARE_SESSION", 0.0)],
        "first view x12 (-> other 5)": [(rules5, "FIRST_VIEW", 5.0)],
        "subcategory x4.5/4 (-> 1)": [(rules5, "SUBCATEGORY", (1.0, 1.0))],
        "category x4.5/3 (-> 1)": [(rules5, "CATEGORY_MAIN", 1.0), (rules5, "CATEGORY_OTHER", 1.0)],
        "segment (-> 1)": [(state, "segment", {})],
        "trend (-> 1)": [(state, "trend", {})],
    }


def ablate_rules5() -> None:
    state = new_state()
    for start, end in CUTS:
        frames = pull_window(f"{DAY} {start}", f"{DAY} {end}")
        reqs, buys, today = purchases(frames)
        tops = {}
        for name, pairs in r5_variants(state).items():
            tops[name] = []
            with patched(pairs):
                for r in reqs.itertuples(index=False):
                    as_of(state, r.u, r.t, buys, today, {})
                    req = Request(r.rid, r.t, r.u, bool(r.new), r.page, r.dev, r.reg, list(r.vp))
                    tops[name].append(guard(rules5.STRATEGY.recommend(req, state), state))
        print(f"cut {start}: rules5 variants on {len(reqs)} purchase requests", flush=True)
        save(reqs, today, tops, f"rules5_{start[:2]}")


def report(prefix: str, ref: str, reps: int = 1000) -> None:
    df = pd.concat([pd.read_parquet(p).assign(cut=p.stem) for p in sorted(DIR.glob(f"{prefix}_*.parquet"))], ignore_index=True)
    rng = np.random.default_rng(0)
    base = df[df["variant"] == ref].set_index(["cut", "rid"])
    print(f"{prefix}: {len(base)} purchase requests over {df['cut'].nunique()} cuts; {ref}: " + ", ".join(
        f"{route} hit1/3/10 " + "/".join(f"{100 * base.loc[base['route'] == route, m].mean():.1f}" for m in ("hit1", "hit3", "hit10"))
        for route in ("main", "new_shopper")))
    print(f"paired variant - {ref}, points ± bootstrap se | main hit1, hit3, hit10 | new_shopper hit1, hit3, hit10 | no_views hit3, hit10 | carted-today hit1, hit3")
    for v in df["variant"].unique():
        if v == ref:
            continue
        cur = df[df["variant"] == v].set_index(["cut", "rid"]).loc[base.index]
        cells = []
        for mask, ms in (((base["route"] == "main").to_numpy(), ("hit1", "hit3", "hit10")), ((base["route"] == "new_shopper").to_numpy(), ("hit1", "hit3", "hit10")),
                         ((base["route"] == "no_views").to_numpy(), ("hit3", "hit10")), (base["carted_today"].to_numpy(), ("hit1", "hit3"))):
            for m in ms:
                dd = (cur[m].to_numpy() - base[m].to_numpy())[mask]
                se = dd[rng.integers(0, len(dd), (reps, len(dd)))].mean(1).std()
                cells.append(f"{100 * dd.mean():+5.1f}±{100 * se:3.1f}")
        print(f"  {v:<40} " + " ".join(cells))


def build_table() -> None:
    state = State()
    state.load()
    s = time.time()
    X, y, b, t, g = train8.table(state)
    DIR.mkdir(parents=True, exist_ok=True)
    np.savez(DIR / "table.npz", X=X, y=y, b=b, t=t, g=g)
    print(f"table {len(y):,} rows, {y.sum():,} clicks, {b.sum():,} purchases in {time.time() - s:.0f} s", flush=True)


if __name__ == "__main__":
    step = sys.argv[1] if len(sys.argv) > 1 else "report"
    if step == "table":
        build_table()
    elif step == "ablate":
        ablate()
    elif step == "select":
        select()
        report("select", "full +rules5_rank")
    elif step == "rules5":
        ablate_rules5()
    else:
        report("ablate", "full")
        report("rules5", "rules5")
