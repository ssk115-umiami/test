"""Passive-quote fill simulator (section 6 Archetype B: `fill_uncertainty`,
`latency_stress_test`).

Deliberately simple and clearly-labeled as such (Gate 9: never claim
executable fills when using naive touch assumptions): fill probability
decays exponentially with how many ticks away from the true best
bid/ask our resting quote sits. `latency_ticks` widens that distance to
simulate stale quotes (a coarse proxy for latency — section 6 explicitly
asks for a latency stress test, not necessarily a queue-position-accurate
one for a 48-hour project, per section 22's scope discipline).
"""

from __future__ import annotations

import numpy as np


class ProbabilisticFillSimulator:
    def __init__(self, fill_decay: float = 1.0, latency_ticks: float = 0.0, rng_seed: int = 0):
        """fill_decay: larger = fill probability drops off faster with
        distance from the touch (in ticks). latency_ticks: added to the
        effective distance for both sides, modeling stale/late quotes."""
        self.fill_decay = fill_decay
        self.latency_ticks = latency_ticks
        self._rng = np.random.default_rng(rng_seed)

    def fill_probabilities(
        self,
        bid_quote: np.ndarray,
        ask_quote: np.ndarray,
        true_best_bid: np.ndarray,
        true_best_ask: np.ndarray,
        tick_size: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        # Our bid fills when a seller crosses it; the closer our bid sits
        # to (or above) the true best bid, the more likely a passing
        # aggressive sell order reaches it.
        bid_distance = np.maximum((true_best_bid - bid_quote) / tick_size, 0) + self.latency_ticks
        ask_distance = np.maximum((ask_quote - true_best_ask) / tick_size, 0) + self.latency_ticks
        bid_fill_prob = np.exp(-self.fill_decay * bid_distance)
        ask_fill_prob = np.exp(-self.fill_decay * ask_distance)
        return bid_fill_prob, ask_fill_prob

    def simulate(
        self,
        bid_quote: np.ndarray,
        ask_quote: np.ndarray,
        true_best_bid: np.ndarray,
        true_best_ask: np.ndarray,
        tick_size: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Returns (bid_filled, ask_filled) boolean arrays via Bernoulli
        draws against the fill probabilities."""
        bid_prob, ask_prob = self.fill_probabilities(bid_quote, ask_quote, true_best_bid, true_best_ask, tick_size)
        bid_filled = self._rng.uniform(size=len(bid_prob)) < bid_prob
        ask_filled = self._rng.uniform(size=len(ask_prob)) < ask_prob
        return bid_filled, ask_filled
