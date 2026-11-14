"""Strategy interface, registry and guard.

A strategy is one file in q2q/strategies/ that defines a module-level STRATEGY.
It reads the live State (see state.py) and returns up to 10 product IDs, best first.
"""
import hashlib
import importlib
from pathlib import Path
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


def label(name: str) -> str:
    """The public model_version of a strategy: other teams see it on the leaderboard, so it says nothing."""
    return "m" + hashlib.sha1(("q2q" + name).encode()).hexdigest()[:5]


def decode(model_version: str) -> str:
    """Strategy name behind a model_version; older answers carry the name itself."""
    code = model_version.split("@")[0]
    names = [f.stem for f in (Path(__file__).parent / "strategies").glob("*.py")]
    return next((n for n in names if label(n) == code), code)
