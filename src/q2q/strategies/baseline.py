"""The starter's logic: all-time best sellers in stock. Also what the guard pads with."""
from q2q.strategy import Strategy


class Baseline(Strategy):
    name = "baseline"

    def recommend(self, req, state):
        return []  # the guard fills the list with state.best


STRATEGY = Baseline()
