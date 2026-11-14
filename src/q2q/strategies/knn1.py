"""Session neighbours 1: ranker2 fused with what other shoppers' sessions bought. docs/hypotheses/H-sql-neighbours.md.

One RawTree query per request: the sessions of other shoppers that viewed one of the request's recent views in the
last HOURS, weighted by which views they share (the newest view counts RECENT times more than the oldest), and the
products those sessions carted (1) or bought (BUY). That list is fused with ranker2's top 10 by reciprocal rank
fusion, as blend1. A timeout, an error or fewer than MIN products answers exactly ranker2's list.

as_of = True makes the query see only events before req.ts (offline replay); live it reads up to now.
Rejected offline (14 Nov): a tie with ranker2 at best, worse than blend1. Not for the router: it answers requests one
at a time, and this adds about 350 ms each.
"""
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError

from q2q import rt
from q2q.strategies import ranker2
from q2q.strategy import Strategy

HOURS = 12
BUY = 2.0
RECENT = 1.0
KEEP_SEEN = True  # the request's own views may be in the list (they are what shoppers buy most)
K = 10.0          # rank damping, as blend1
WEIGHT = 0.3      # the neighbour list's weight against ranker2's 1.0
MIN = 1
TIMEOUT = 0.6     # seconds, hard: the answer deadline is 3 s
SQL = """WITH s AS (SELECT session_id::String AS sid,
    arraySum(arrayMap(v -> transform(v, [{VIEWS}], [{WEIGHTS}], 0.0), groupUniqArray(product_id::String))) AS ov
  FROM shop.events WHERE {WIN} AND event_type::String = 'view' AND product_id::String IN ({VIEWS}) AND user_id::String != '{USER}'
  GROUP BY sid)
SELECT e.product_id::String AS p, sum(s.ov * if(e.event_type::String = 'purchase', {BUY}, 1.0)) AS w
FROM shop.events e INNER JOIN s ON e.session_id::String = s.sid
WHERE {EWIN} AND e.event_type::String IN ('purchase', 'add_to_cart'){EXCL}
GROUP BY p ORDER BY w DESC, p LIMIT 20 SETTINGS max_execution_time = 1"""
_pool = ThreadPoolExecutor(4)


def sql(views: list[str], user: str, as_of: float | None = None) -> str:
    views = list(dict.fromkeys(reversed(views)))[::-1]   # distinct, oldest first, a repeat counts at its newest position
    n = len(views)
    now = f"toDateTime64({as_of:.3f}, 3)" if as_of else "now64(3)"
    win = f"ts::DateTime64(3) >= {now} - INTERVAL {HOURS} HOUR AND ts::DateTime64(3) < {now}"
    clean = lambda s: s.replace("'", "")  # noqa: E731 - ids come from the request
    excl = "" if KEEP_SEEN else " AND e.product_id::String NOT IN ({VIEWS})"
    return (SQL.replace("{EXCL}", excl).replace("{EWIN}", win.replace("ts::", "e.ts::")).replace("{WIN}", win)
            .replace("{VIEWS}", ",".join(f"'{clean(v)}'" for v in views))
            .replace("{WEIGHTS}", ",".join(f"{1 + RECENT * i / max(n - 1, 1):.3f}" for i in range(n)))
            .replace("{USER}", clean(user)).replace("{BUY}", str(BUY)))


def neighbours(views: list[str], user: str, as_of: float | None = None) -> list[str]:
    return [r["p"] for r in rt.query(sql(views, user, as_of), timeout=TIMEOUT)]


class Knn1(Strategy):
    name = "knn1"
    as_of = False

    def recommend(self, req, state):
        if not req.views:
            return ranker2.STRATEGY.recommend(req, state)
        start = time.monotonic()
        job = _pool.submit(neighbours, req.views, req.user_id, req.ts if self.as_of else None)
        base = ranker2.STRATEGY.recommend(req, state)   # while the query runs
        try:
            nb = job.result(timeout=max(0.0, TIMEOUT - (time.monotonic() - start)))
        except (TimeoutError, Exception):
            return base
        if len(nb) < MIN:
            return base
        score = {}
        for w, items in ((1.0, base), (WEIGHT, nb[:10])):
            for i, pid in enumerate(items):
                score[pid] = score.get(pid, 0.0) + w / (K + i)
        return sorted(score, key=score.get, reverse=True)[:10]


STRATEGY = Knn1()
