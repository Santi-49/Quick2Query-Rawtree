from dataclasses import dataclass, field

from q2q.strategies.rules5 import LAST_VIEW, ONLY_VIEW, TODAY_CART, Rules5
from q2q.strategy import Request


@dataclass
class P:
    id: str
    category: str
    subcategory: str
    appeal: float
    views: int = 1000
    buys: int = 200
    is_new: bool = False


@dataclass
class Shopper:
    bought: set = field(default_factory=set)
    viewed: dict = field(default_factory=dict)
    cat_share: dict = field(default_factory=dict)
    carted: dict = field(default_factory=dict)


class FakeState:
    def __init__(self):
        self.products = {f"p{i}": P(f"p{i}", f"c{i % 3}", f"s{i % 6}", 1.0) for i in range(60)}
        self.by_category, self.by_subcategory = {}, {}
        for p in self.products.values():
            self.by_category.setdefault(p.category, []).append(p.id)
            self.by_subcategory.setdefault(p.subcategory, []).append(p.id)
        self.best = list(self.products)
        self.segment, self.trend, self.price_cut = {}, {}, {}
        self.shoppers = {"known": Shopper(bought={"p3"}, viewed={"p20": 1, "p21": 5},
                                          carted={"p20": 1, "p21": 1, "p40": 1})}
        self._today_carts = {"known": {"p40": 1}}

    def available(self, pid):
        return pid != "p0"

    def shopper(self, user_id):
        return self.shoppers.get(user_id)

    def today_views(self, user_id):
        return []


def request(views, user="known"):
    return Request("r", 0.0, user, False, "product" if views else "home", "web", "ES", list(views))


def test_today_cart_leads_and_valid():
    state = FakeState()
    rows = Rules5().explain(request(["p1", "p7"]), state)
    out = [pid for _, pid, _ in rows]
    assert len(out) == len(set(out)) == 10 and "p0" not in out and "p3" not in out
    assert out[0] == "p40" and rows[0][2]["session"] == TODAY_CART  # carted today beats the first view
    parts = {pid: p for _, pid, p in rows}
    assert parts["p20"]["session"] > parts.get("p21", {"session": 0})["session"]  # a carted product viewed once beats one viewed 5 times


def test_view_positions():
    state = FakeState()
    one = {pid: p for _, pid, p in Rules5().explain(request(["p1", "p1"], user="nobody"), state)}
    assert one["p1"]["session"] == ONLY_VIEW
    many = {pid: p for _, pid, p in Rules5().explain(request(["p1", "p7", "p2"], user="nobody"), state)}
    assert "p2" not in many or many["p2"]["session"] == LAST_VIEW  # the last of several views ranks below its own subcategory (4.5)


def test_home_and_unknown_products():
    state = FakeState()
    for views in ([], ["zzz"]):
        out = Rules5().recommend(request(views), state)
        assert len(out) == len(set(out)) == 10 and "p0" not in out and "p3" not in out
        assert {"p20", "p21", "p40"} <= set(out)  # carted products lead the home list
