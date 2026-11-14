"""Strategy interface, registry and guard.

A strategy is one file in q2q/strategies/ that defines a module-level STRATEGY.
It reads the live State (see state.py) and returns up to 10 product IDs, best first.
"""
import importlib
from dataclasses import dataclass, field

N = 10


@dataclass(slots=True)
class Request:
    request_id: str
    ts: float              # epoch seconds, UTC
    user_id: str
    is_new_user: bool
    page: str              # product, category, home
    device: str            # android, ios, web
    region: str
    views: list[str]       # recent views, oldest first
    log: dict = field(default_factory=dict)  # a strategy may leave facts here; the router stores them (explore arm)


class Strategy:
    name = "strategy"

    def recommend(self, req: Request, state) -> list[str]:
        raise NotImplementedError

    def learn(self, feedback_rows: list[dict]) -> None:
        """Optional online update from our feedback rows."""


def load(name: str, reload: bool = False) -> Strategy:
    module = importlib.import_module(f"q2q.strategies.{name}")
    if reload:
        module = importlib.reload(module)
    return module.STRATEGY


def guard(items: list[str], state) -> list[str]:
    """Always a valid answer: available, no duplicates, padded with best sellers to N."""
    out, seen = [], set()
    for source in (items, state.best):
        for p in source:
            if len(out) == N:
                return out
            if p not in seen and state.available(p):
                seen.add(p)
                out.append(p)
    return out
