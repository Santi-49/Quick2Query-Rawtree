"""Super 2: super1 with only the two signals that led live, purchase taste (aff1) and the last-category boost (lock3).

Read at 07:10 UTC (30 min, about 700 requests per arm on main): aff1 +59.4 and lock3 +58.2 against ranker2 +48.5,
while super1 (also the live subcategory rate and hot products) scored +48.0. The background tables stay empty,
so their factors are 1. Label: hash.
"""
from q2q.strategies.super1 import Super1


class Super2(Super1):
    name = "super2"

    def __init__(self):
        super().__init__()
        self.built = float("inf")   # never refresh: no subcategory or hot-product factors


STRATEGY = Super2()
