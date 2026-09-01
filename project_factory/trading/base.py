"""Trading / decision-layer contract (section 11.5).

Prediction alone is not enough for a trading role (section 3.5): every
predictive model here must be run through a Strategy that turns a
prediction into a position/quote decision, then into PnL under realistic
costs/constraints.
"""

from __future__ import annotations

from typing import Protocol

import pandas as pd


class Strategy(Protocol):
    def decisions(self, predictions: pd.Series, market_state: pd.DataFrame, spec) -> pd.DataFrame:
        """Turn model predictions + current market state into position/
        quote decisions (one row per decision point)."""
        ...

    def evaluate(self, decisions: pd.DataFrame, realized: pd.DataFrame, spec) -> dict:
        """Simulate fills/PnL against what actually happened next and
        return trading metrics (+ the per-row PnL series for diagnostics)."""
        ...
