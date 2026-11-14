from dataclasses import dataclass, field

from q2q.strategies.rules4 import CARTED, CATEGORY_MAIN, CATEGORY_OTHER, FIRST_VIEW, OTHER_VIEW, Rules4, main_category
from q2q.strategy import Request


@dataclass
class P:
    id: str
    category: str
    subcategory: str
    appeal: float


@dataclass
class Shopper:
    bought: set = field(default_factory=set)
    viewed: dict = field(default_factory=dict)
    cat_share: dict = field(default_factory=dict)


class FakeState:
    def __init__(self):
        self.products = {f"p{i}": P(f"p{i}", f"c{i % 3}", f"s{i % 6}", 1.0) for i in range(60)}
        self.by_category, self.by_subcategory = {}, {}
        for p in sorted(self.products.values(), key=lambda p: -p.appeal):
            self.by_category.setdefault(p.category, []).append(p.id)
            self.by_subcategory.setdefault(p.subcategory, []).append(p.id)
        self.segment, self.trend, self.price_cut = {}, {}, {}
        self.shoppers = {"known": Shopper(bought={"p3", "p9"}, viewed={"p4": 2}, cat_share={"c1": 0.5, "c0": 0.5})}

    def available(self, pid):
        return pid != "p0"

    def shopper(self, user_id):
        return self.shoppers.get(user_id)


def request(views, user="known"):
    return Request("r", 0.0, user, False, "category", "web", "ES", list(views))


def test_category_page_mixed_views():
    state = FakeState()
    views = ["p1", "p4", "p7", "p3", "p2"]  # categories c1, c1, c1, c0, c2: main c1, last c2
    out = Rules4().recommend(request(views), state)
    assert len(out) == len(set(out)) == 10
    assert all(state.available(p) and p in state.products for p in out)
    assert not {"p3", "p9"} & set(out)  # never a bought product, even a recent view
    assert out[0] == "p1"  # the first view leads


def test_relation_values():
    state = FakeState()
    rows = {pid: parts for _, pid, parts in Rules4().explain(request(["p1", "p7", "p2"], user="nobody"), state)}
    assert rows["p1"]["session"] == FIRST_VIEW
    assert rows["p2"]["session"] == OTHER_VIEW  # the last view counts as a later view
    assert main_category([state.products[p] for p in ("p1", "p7", "p2")]) == "c1"
    assert main_category([state.products[p] for p in ("p2", "p1")]) == "c2"  # tie: the earliest view
    assert main_category([]) is None
    others = [parts["session"] for _, pid, parts in Rules4().explain(request(["p1", "p7", "p2"], user="nobody"), state)
              if pid not in ("p1", "p7", "p2")]
    assert all(s in (CATEGORY_MAIN, CATEGORY_OTHER, 4.5, 4.0, 1.0) for s in others)


def test_carted_beats_viewed_only():
    state = FakeState()
    state.shoppers["carts"] = Shopper(viewed={"p20": 3, "p21": 3}, cat_share={"c2": 1.0})
    state.shoppers["carts"].carted = {"p20": 1}
    rows = {pid: parts for _, pid, parts in Rules4().explain(request(["p1"], user="carts"), state)}
    assert rows["p20"]["session"] == CARTED  # p20 is c2, outside the session category c1
    assert "p21" not in rows or rows["p21"]["session"] == 1.0
    old = {pid: parts for _, pid, parts in Rules4().explain(request(["p1"]), state)}  # no carted attribute: rules2's view bonus
    assert old["p4"]["viewed before"] > 1


def test_no_views_and_unknown_products():
    state = FakeState()
    for views in ([], ["zzz"], ["zzz", "p5"]):
        out = Rules4().recommend(request(views, user="nobody"), state)
        assert len(out) == len(set(out)) == 10 and "p0" not in out
