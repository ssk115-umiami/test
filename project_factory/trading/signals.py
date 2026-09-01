"""Predicted-probability -> quoting decision -> simulated PnL
(section 6 Archetype B's reservation-price formula):

    r_t = m_t + alpha * mu_hat_t - gamma * q_t

`decisions()` computes the alpha-only component (mu_hat) deterministically
per row. `evaluate()` runs the stateful loop that also needs the running
inventory (q_t): computes the actual reservation price and quotes,
simulates fills against the true touch, and returns a full trading-metrics
dict plus the per-row PnL series diagnostics needs.

Setting alpha=0 reproduces the "no_alpha_symmetric_market_maker" baseline
from the archetype's model ladder (section 6) — it's the trading-layer
baseline, not a ResearchModel, because it's a quoting rule, not a
prediction.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from project_factory.trading.costs import fee_amount
from project_factory.trading.execution.fill_simulator import ProbabilisticFillSimulator
from project_factory.trading.inventory import clip_inventory, inventory_skew
from project_factory.trading.pnl import compute_equity_curve, compute_pnl_series, max_drawdown, sharpe_ratio, turnover


class MarketMakingStrategy:
    def __init__(
        self,
        alpha: float = 1.0,
        gamma: float = 0.1,
        half_spread_ticks: float = 2.0,
        order_size: float = 1.0,
        max_inventory: float = 10.0,
        fee_bps: float = 1.0,
        fill_decay: float = 1.0,
        latency_ticks: float = 0.0,
        rng_seed: int = 0,
    ):
        self.alpha = alpha
        self.gamma = gamma
        self.half_spread_ticks = half_spread_ticks
        self.order_size = order_size
        self.max_inventory = max_inventory
        self.fee_bps = fee_bps
        self.fill_decay = fill_decay
        self.latency_ticks = latency_ticks
        self.rng_seed = rng_seed

    def decisions(self, predictions: pd.Series, market_state: pd.DataFrame, spec=None) -> pd.DataFrame:
        required = {"timestamp", "mid_price", "bid_price_1", "ask_price_1", "spread"}
        missing = required - set(market_state.columns)
        if missing:
            raise ValueError(f"market_state missing required columns: {missing}")

        tick_size = np.maximum(market_state["spread"].to_numpy() / 4.0, 1e-8)
        mu_hat = self.alpha * (2.0 * predictions.to_numpy() - 1.0)

        return pd.DataFrame(
            {
                "timestamp": market_state["timestamp"].to_numpy(),
                "mid_price": market_state["mid_price"].to_numpy(),
                "true_best_bid": market_state["bid_price_1"].to_numpy(),
                "true_best_ask": market_state["ask_price_1"].to_numpy(),
                "tick_size": tick_size,
                "mu_hat": mu_hat,
            }
        )

    def evaluate(self, decisions: pd.DataFrame, realized: pd.DataFrame | None = None, spec=None) -> dict:
        n = len(decisions)
        mid_price = decisions["mid_price"].to_numpy()
        true_best_bid = decisions["true_best_bid"].to_numpy()
        true_best_ask = decisions["true_best_ask"].to_numpy()
        tick_size = decisions["tick_size"].to_numpy()
        mu_hat = decisions["mu_hat"].to_numpy()

        inventory = np.zeros(n)
        cash = np.zeros(n)
        bid_quote = np.zeros(n)
        ask_quote = np.zeros(n)
        bid_filled = np.zeros(n, dtype=bool)
        ask_filled = np.zeros(n, dtype=bool)

        simulator = ProbabilisticFillSimulator(
            fill_decay=self.fill_decay, latency_ticks=self.latency_ticks, rng_seed=self.rng_seed
        )
        rng = np.random.default_rng(self.rng_seed)

        prev_inventory = 0.0
        prev_cash = 0.0
        for t in range(n):
            reservation_price = mid_price[t] + mu_hat[t] * tick_size[t] + inventory_skew(prev_inventory, self.gamma)
            bid_quote[t] = reservation_price - self.half_spread_ticks * tick_size[t]
            ask_quote[t] = reservation_price + self.half_spread_ticks * tick_size[t]

            bid_prob, ask_prob = simulator.fill_probabilities(
                np.array([bid_quote[t]]), np.array([ask_quote[t]]),
                np.array([true_best_bid[t]]), np.array([true_best_ask[t]]),
                np.array([tick_size[t]]),
            )
            filled_bid = rng.uniform() < bid_prob[0]
            filled_ask = rng.uniform() < ask_prob[0]

            new_inventory = prev_inventory
            new_cash = prev_cash
            if filled_bid and clip_inventory(prev_inventory + self.order_size, self.max_inventory) != prev_inventory:
                new_inventory += self.order_size
                notional = bid_quote[t] * self.order_size
                new_cash -= notional + fee_amount(notional, self.fee_bps)
                bid_filled[t] = True
            if filled_ask and clip_inventory(new_inventory - self.order_size, self.max_inventory) != new_inventory:
                new_inventory -= self.order_size
                notional = ask_quote[t] * self.order_size
                new_cash += notional - fee_amount(notional, self.fee_bps)
                ask_filled[t] = True

            inventory[t] = new_inventory
            cash[t] = new_cash
            prev_inventory, prev_cash = new_inventory, new_cash

        equity = compute_equity_curve(cash, inventory, mid_price)
        pnl = compute_pnl_series(equity)
        fill_sizes = np.where(bid_filled, self.order_size, 0.0) - np.where(ask_filled, self.order_size, 0.0)

        n_quotes = 2 * n
        n_fills = int(bid_filled.sum() + ask_filled.sum())

        return {
            "total_pnl": float(equity[-1] - equity[0]),
            "sharpe": sharpe_ratio(pnl),
            "max_drawdown": max_drawdown(equity),
            "fill_rate": n_fills / n_quotes if n_quotes else 0.0,
            "n_fills": n_fills,
            "turnover": turnover(fill_sizes),
            "avg_inventory": float(np.mean(inventory)),
            "max_abs_inventory": float(np.max(np.abs(inventory))),
            "final_inventory": float(inventory[-1]),
            "equity_curve": equity.tolist(),
            "pnl_series": pnl.tolist(),
            "inventory_series": inventory.tolist(),
        }
