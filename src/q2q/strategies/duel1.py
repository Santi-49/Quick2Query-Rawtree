"""Duel 1: team-draft interleaving of two strategies on one screen.

Each round a coin (bits of sha1(request_id)) picks which side goes first; each side adds its best product not yet
shown. Every product is credited to the side that picked it, and the credit goes to team_01.scratch as kind 'duel'
rows from a background thread. scripts/duel.py scores it. docs/hypotheses/H-interleave.md.
"""
import hashlib
import sys
import threading
import time
from datetime import datetime, timezone

from q2q.strategies import blend1, ranker2
from q2q.strategy import Strategy

A, B = "ranker2", "blend1"
SOURCES = {"ranker2": ranker2.STRATEGY, "blend1": blend1.STRATEGY}
LOG = True          # tests turn it off
FLUSH_S, FLUSH_ROWS, CAP = 30, 200, 5000

BUF: list[dict] = []
LOCK = threading.Lock()
WAKE = threading.Event()
_started = False


def interleave(request_id: str, a: list[str], b: list[str], n: int = 10) -> tuple[list[str], list[str], list[str]]:
    """Shown list, products credited to a, products credited to b."""
    bits = int.from_bytes(hashlib.sha1(request_id.encode()).digest()[:4], "big")
    out, seen, credit = [], set(), ([], [])
    pos = [0, 0]
    lists = (a, b)
    for r in range(n):
        first = (bits >> r) & 1
        moved = False
        for side in (first, 1 - first):
            if len(out) == n:
                break
            lst = lists[side]
            while pos[side] < len(lst) and lst[pos[side]] in seen:
                pos[side] += 1
            if pos[side] < len(lst):
                pid = lst[pos[side]]
                seen.add(pid)
                out.append(pid)
                credit[side].append(pid)
                moved = True
        if not moved or len(out) == n:
            break
    return out, credit[0], credit[1]


def _flush_loop(buf: list[dict]) -> None:
    from q2q import rt
    while True:
        WAKE.wait(FLUSH_S)
        WAKE.clear()
        with LOCK:
            rows = buf[:]
            buf.clear()
        if rows:
            try:
                rt.insert("scratch", rows)
            except Exception:
                with LOCK:
                    buf[:0] = rows
                    del buf[:-CAP]   # keep the newest CAP rows
        if getattr(sys.modules.get(__name__), "BUF", None) is not buf and not buf:
            return   # the module was reloaded and this buffer is drained


class Duel1(Strategy):
    name = "duel1"

    def recommend(self, req, state):
        global _started
        a = SOURCES[A].recommend(req, state)
        b = SOURCES[B].recommend(req, state)
        out, a_items, b_items = interleave(req.request_id, a, b)
        if LOG:
            row = {"kind": "duel", "ts": datetime.fromtimestamp(req.ts, timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                   "request_id": req.request_id, "a": A, "b": B, "a_items": a_items, "b_items": b_items}
            with LOCK:
                BUF.append(row)
                if len(BUF) > CAP:
                    del BUF[0]
                if not _started:
                    _started = True
                    threading.Thread(target=_flush_loop, args=(BUF,), daemon=True, name="duel1-flush").start()
            if len(BUF) >= FLUSH_ROWS:
                WAKE.set()
        return out


STRATEGY = Duel1()
