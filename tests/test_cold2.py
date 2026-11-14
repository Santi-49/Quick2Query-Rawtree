from dataclasses import dataclass, field

from q2q.strategies.cold2 import Cold2
from q2q.strategy import Request


@dataclass
class P:
    id: str
    category: str
    subcategory: str
    buys: int
    is_new: bool = False
    appeal: float = 0.1


@dataclass
class Shopper:
    bought: set = field(default_factory=set)
    viewed: dict = field(default_factory=dict)
    cat_share: dict = field(default_factory=dict)


class FakeState:
    def __init__(self):
        self.products = {f"p{i}": P(f"p{i}", f"c{i % 3}", f"s{i % 6}", 100 - i) for i in range(60)}
        self.products["n0"] = P("n0", "c1", "s1", 0, is_new=True, appeal=2.0)
        self.best = [f"p{i}" for i in range(60)]
        self.by_category, self.by_subcategory = {}, {}
        for p in self.products.values():
            self.by_category.setdefault(p.category, []).append(p.id)
            self.by_subcategory.setdefault(p.subcategory, []).append(p.id)
        self.segment = {("android", "Murcia"): {"c2": 5.0}}
        self.trend = {"s4": 2.0}
        self.shoppers = {"known": Shopper(bought={"p0", "p3", "p6"}, viewed={"p9": 3, "p12": 1}, cat_share={"c0": 0.7, "c1": 0.3})}

    def available(self, pid):
        return pid != "p1"

    def shopper(self, user_id):
        return self.shoppers.get(user_id)


def request(user, new=False):
    return Request("r", 0.0, user, new, "home", "android", "Murcia", [])


def check(items, state, bought=()):
    assert len(items) == len(set(items)) == 10
    assert all(p in state.products and state.available(p) for p in items)
    assert not set(items) & set(bought)


def test_returning_new_and_unknown():
    state, s = FakeState(), Cold2()
    known = s.recommend(request("known"), state)
    check(known, state, state.shoppers["known"].bought)
    assert all(state.products[p].category == "c0" for p in known[:3])  # top category leads
    new = s.recommend(request("brand-new", new=True), state)
    check(new, state)
    assert state.products[new[0]].category == "c2"  # segment lift x5 on c2
    check(s.recommend(request("nobody"), state), state)


def test_never_bought_even_with_cart_and_today():
    state, s = FakeState(), Cold2()
    shopper = state.shoppers["known"]
    shopper.carted = {"p30": 2, "p0": 3}   # optional state: p0 is bought, must stay out
    state.today_views = lambda u: ["p3", "p40"]
    items = s.recommend(request("known"), state)
    check(items, state, shopper.bought)
    assert items[0] == "p30"


def test_explain_parts():
    state, s = FakeState(), Cold2()
    out = s.explain(request("known"), state)
    assert len(out) == 10
    for score, pid, parts in out:
        assert score > 0 and set(parts) >= {"best seller", "category rank", "cart", "segment"}
