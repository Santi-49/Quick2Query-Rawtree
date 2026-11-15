"""Race 1: super1 fed by a per-shopper SQL query when it answers in time, else super1 from memory.

Santi's idea (15 Nov): query the shopper's last 24 h of shop.events at request time (0.5-0.7 s measured) and use
it if it arrives before the deadline budget, else the in-memory answer. The query sees views older than the
memory's 2 h window and purchases up to the moment. The wait blocks the router's loop, so it is capped at WAIT
and run on a small share of traffic. Counts of SQL answers and fallbacks go to the router log. Label: hash.
"""
import threading
import time

from q2q import rt
from q2q.strategies import ranker2
from q2q.strategies.super1 import Super1

WAIT, DEADLINE, MARGIN = 1.0, 2.5, 0.8   # seconds: longest wait; answer by DEADLINE after the request, MARGIN for the push
SQL = """SELECT event_type::String AS et, product_id::String AS p FROM shop.events
WHERE user_id::String = '{u}' AND ts::DateTime64(3) > now() - INTERVAL 24 HOUR ORDER BY ts::DateTime64(3)"""


class Race1(Super1):
    name = "race1"

    def __init__(self):
        super().__init__()
        self.counts = {"sql": 0, "memory": 0}

    def recommend(self, req, state):
        base = ranker2.STRATEGY
        wait = min(WAIT, DEADLINE - MARGIN - (time.time() - req.ts))
        if base.models is None or wait < 0.2 or not req.user_id.replace("_", "").isalnum():
            return self.fallback(req, state)
        box = []
        t = threading.Thread(target=lambda: box.append(rt.query(SQL.replace("{u}", req.user_id))), daemon=True)
        t.start()
        t.join(wait)
        if not box:
            return self.fallback(req, state)
        self.counts["sql"] += 1
        self.log()
        rows = box[0]
        today = list(dict.fromkeys(r["p"] for r in reversed(rows) if r["et"] == "view"))[::-1]
        bought = set(state._live.get(req.user_id, ())) | {r["p"] for r in rows if r["et"] == "purchase"}
        if time.time() - self.built > 600 and not self.busy:   # super1's background tables
            self.busy = True
            threading.Thread(target=self._refresh, args=(state,), daemon=True).start()
        return self.rank(req, state, today, bought)

    def fallback(self, req, state):
        self.counts["memory"] += 1
        self.log()
        return super().recommend(req, state)

    def log(self):
        n = sum(self.counts.values())
        if n % 20 == 0:
            print(f"race1: {self.counts['sql']} SQL answers, {self.counts['memory']} from memory", flush=True)


STRATEGY = Race1()
