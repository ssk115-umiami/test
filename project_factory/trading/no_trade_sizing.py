"""Forecast -> position-sizing decision -> simulated PnL for Archetype A
(power regime / DA-RT research, section 6): "forecast uncertainty ->
no-trade / sizing rule" rather than a quoting strategy.

Reuses trading/costs.py (fees) and trading/pnl.py's
assemble_periodic_trading_result the same way MarketMakingStrategy
reuses assemble_trading_result — this is the concrete piece of shared
trading-layer infrastructure Milestone 4 was meant to test for.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from project_factory.trading.costs import fee_amount
from project_factory.trading.pnl import assemble_periodic_trading_result


class NoTradeSizingStrategy:
    def __init__(
        self,
        no_trade_threshold: float = 1.0,
        max_position: float = 5.0,
        size_scale: float = 1.0,
        fee_bps: float = 2.0,
    ):
        """no_trade_threshold: predicted |spread| below this -> flat
        (the "no-trade" band — section 6's uncertainty-aware sizing
        rule). size_scale: converts a predicted spread into a position
        size; max_position caps it. fee_bps: cost charged on each unit
        of position CHANGE (a trade), not on the position itself."""
        self.no_trade_threshold = no_trade_threshold
        self.max_position = max_position
        self.size_scale = size_scale
        self.fee_bps = fee_bps

    def decisions(self, predictions: pd.Series, market_state: pd.DataFrame, spec=None) -> pd.DataFrame:
        if "timestamp" not in market_state.columns:
            raise ValueError("market_state must include a 'timestamp' column")

        pred = predictions.to_numpy()
        raw_size = np.clip(pred * self.size_scale, -self.max_position, self.max_position)
        position = np.where(np.abs(pred) > self.no_trade_threshold, raw_size, 0.0)

        return pd.DataFrame(
            {
                "timestamp": market_state["timestamp"].to_numpy(),
                "predicted_spread": pred,
                "position_size": position,
            }
        )

    def evaluate(self, decisions: pd.DataFrame, realized: pd.DataFrame, spec=None) -> dict:
        if "da_rt_spread" not in realized.columns:
            raise ValueError("realized must include the 'da_rt_spread' column to score positions against")

        position = decisions["position_size"].to_numpy()
        realized_spread = realized["da_rt_spread"].to_numpy()
        if len(position) != len(realized_spread):
            raise ValueError("decisions and realized must have the same length (same rows, same order)")

        gross_period_pnl = position * realized_spread
        position_changes = np.diff(position, prepend=0.0)
        fees = fee_amount(position_changes, self.fee_bps)
        net_period_pnl = gross_period_pnl - fees

        traded = position_changes
        n_trades = int(np.sum(np.abs(position_changes) > 1e-12))
        fill_rate = float(np.mean(np.abs(position) > 1e-12))  # fraction of periods with an open position

        return assemble_periodic_trading_result(
            position=position,
            period_pnl=net_period_pnl,
            traded_notional=traded,
            fill_rate=fill_rate,
            n_fills=n_trades,
        )
