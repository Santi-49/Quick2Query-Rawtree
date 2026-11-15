"""Lock 3: a soft lock1. In-category scores x BOOST instead of a hard lock.

Case study of the last 3 h of purchases on view requests (546): 56% were in the last view's category, but about 21%
were cross-category items, mostly Books & Media and Toys & Baby, and half of those sold from slot 1. A hard lock
drops them; a x2 boost keeps a strong cross-category item and still fills most of the row from the category.
Label: the hash name, so the router needs no restart.
"""
from q2q.strategies.lock1 import Lock1


class Lock3(Lock1):
    name = "lock3"
    boost = 2.0


STRATEGY = Lock3()
