"""Leak-free check of the model strategies: train ranker and ranker2 on feedback before the replay window, then replay.

    uv run eda/replay/holdout.py 2        # window = last 2 hours; models fitted on everything before it

The holdout models go to data/replay/models/, never models/ (the router reads that folder).
The window's cache is the same as q2q replay --hours 2.
"""
import sys

from q2q import replay, rt, train, train2
from q2q.state import State, epoch
from q2q.strategies import ranker, ranker2

DIR = rt.ROOT / "data" / "replay" / "models"


def main(hours: float) -> None:
    frames = replay.pull(hours, refresh=False)
    cut_ms = epoch(frames["meta"].iloc[0]["start"]) * 1000
    print(f"training on feedback before {frames['meta'].iloc[0]['start']} UTC", flush=True)
    DIR.mkdir(parents=True, exist_ok=True)
    train.MODEL = ranker.MODEL = DIR / "ranker.txt"
    train2.MODEL = ranker2.MODEL = DIR / "ranker2.txt"
    train2.BUY_MODEL = ranker2.BUY_MODEL = DIR / "ranker2_buy.txt"
    state = State()
    state.load()
    query = rt.query
    rt.query = lambda sql, timeout=30: [r for r in query(sql, timeout) if not ("t" in r and float(r["t"]) >= cut_ms)]
    train.train(state)
    train2.train(state)
    rt.query = query
    replay.run(["rules2", "rules4", "ranker", "ranker2"], hours)


if __name__ == "__main__":
    main(float(sys.argv[1]) if len(sys.argv) > 1 else 2)
