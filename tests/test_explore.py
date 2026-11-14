from dataclasses import dataclass, field

from q2q.strategies.explore import BASE, Explore
from q2q.strategy import Request


@dataclass
class P:
    id: str
    category: str
    subcategory: str


@dataclass
class Shopper:
    bought: set = field(default_factory=set)
    viewed: dict = field(default_factory=dict)
    cat_share: dict = field(default_factory=dict)


class FakeState:
    def __init__(self):
        self.products = {f"p{i}": P(f"p{i}", f"c{i % 3}", f"s{i % 6}") for i in range(60)}
        self.by_category, self.by_subcategory = {}, {}
        for p in self.products.values():
            self.by_category.setdefault(p.category, []).append(p.id)
            self.by_subcategory.setdefault(p.subcategory, []).append(p.id)
        self.new_products = ["p50", "p51", "p52"]
        self.shoppers = {"known": Shopper(viewed={"p1": 3, "p2": 1, "p4": 2})}

    def available(self, pid):
        return pid != "p0"

    def shopper(self, user_id):
        return self.shoppers.get(user_id)


def request(user="known", views=("zzz", "p7", "p8", "p7", "unknown")):
    return Request("r", 0.0, user, False, "product", "web", "ES", list(views))


def test_every_stratum_drawn_and_propensity():
    s, state = Explore(), FakeState()
    s.rng.seed(1)
    seen = set()
    for _ in range(2000):
        req = request()
        items = s.recommend(req, state)
        log = req.log
        seen.add(log["stratum"])
        assert log["n"] == len(items) == len(set(items)) <= 10
        assert all(state.available(p) for p in items)
        assert abs(log["p_stratum"] - BASE[log["stratum"]]) < 1e-9  # all pools non-empty here
        assert abs(log["propensity"] - log["p_stratum"] * min(1, 10 / log["pool"])) < 1e-9
        if log["stratum"] == "recent":
            assert sorted(items) == ["p7", "p8"]
        if log["stratum"] == "favourites":
            assert sorted(items) == ["p1", "p4"]
        if log["stratum"] == "subcategory":  # last known view is p7
            assert all(state.products[p].subcategory == "s1" for p in items)
    assert seen == set(BASE)


def test_favourites_fall_back_to_largest_category():
    s, state = Explore(), FakeState()
    state.shoppers["known"] = Shopper(viewed={"p1": 1}, cat_share={"c0": 0.2, "c2": 0.8})
    s.rng.seed(2)
    for _ in range(500):
        req = request()
        items = s.recommend(req, state)
        if req.log["stratum"] == "favourites":
            assert all(state.products[p].category == "c2" for p in items)
            return
    raise AssertionError("favourites never drawn")


def test_no_views_unknown_shopper_only_new_or_anything():
    s, state = Explore(), FakeState()
    s.rng.seed(3)
    strata = set()
    for _ in range(500):
        req = request(user="nobody", views=())
        s.recommend(req, state)
        strata.add(req.log["stratum"])
        expected = {"new": 0.4, "anything": 0.6}[req.log["stratum"]]
        assert abs(req.log["p_stratum"] - expected) < 1e-9
    assert strata == {"new", "anything"}
