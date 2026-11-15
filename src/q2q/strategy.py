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


PUBLIC = {"baseline": "quartz", "explore": "mica", "rules": "flint", "rules2": "slate", "rules3": "basalt",
          "cold1": "opal", "ranker": "jasper", "cold2": "agate", "rules4": "onyx", "ranker2": "shale",
          "rules5": "garnet", "linear1": "pyrite"}
"""Public model_version per strategy: other teams see it on the leaderboard, so it is a word that says nothing.
Add a line for every new model, and a VARIANT line for a variant of one."""
OLD = {"baseline": "coca", "explore": "xuixo", "rules": "mato", "rules2": "romesco", "rules3": "fideua", "cold1": "panellet"}


ROUTES = {"": "", "no_views": "-h", "new_shopper": "-n"}
"""Suffix per kind of request, so the per-model leaderboard compares arms on the same kind of request."""


VARIANT = {"blend1": ("ranker2", "b"), "ranker6": ("ranker2", "c"), "ranker7": ("ranker2", "d"), "ranker8": ("ranker2", "e"),
           "knn1": ("ranker2", "k"), "pin1": ("ranker2", "p"), "lock1": ("ranker2", "l")}
"""Variants and ablations of one model: (the model, a letter). They show as the model's public word plus the letter in capitals: only letters, digits and "-" are known to be accepted."""


def _hash(name: str) -> str:
    return "m" + hashlib.sha1(("q2q" + name).encode()).hexdigest()[:5]


def _word(name: str) -> str:
    if name in VARIANT:
        return _word(VARIANT[name][0]) + VARIANT[name][1].upper()
    return PUBLIC.get(name) or _hash(name)


def label(name: str, route: str = "") -> str:
    return _word(name) + ROUTES[route]


def decode(model_version: str) -> str:
    """Strategy name behind a model_version, in any of the forms we have sent."""
    code = model_version.split("@")[0].split("-")[0]
    names = list(PUBLIC) + list(VARIANT) + [f.stem for f in (Path(__file__).parent / "strategies").glob("*.py")]
    return next((n for n in names if code in (_word(n), OLD.get(n), _hash(n))), code)


def route_of(model_version: str) -> str:
    suffix = "-" + model_version.split("-")[1] if "-" in model_version else ""
    return next((r for r, s in ROUTES.items() if s == suffix), "")
