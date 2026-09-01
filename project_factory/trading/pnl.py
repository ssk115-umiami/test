"""PnL / risk metrics from a simulated cash + inventory path."""

from __future__ import annotations

import numpy as np


def compute_equity_curve(cash: np.ndarray, inventory: np.ndarray, mid_price: np.ndarray) -> np.ndarray:
    """Mark-to-market equity at each step: cash plus inventory valued at
    the current mid price."""
    return cash + inventory * mid_price


def compute_pnl_series(equity: np.ndarray) -> np.ndarray:
    pnl = np.diff(equity, prepend=equity[0])
    pnl[0] = 0.0
    return pnl


def sharpe_ratio(pnl: np.ndarray, periods_per_year: float | None = None) -> float:
    std = pnl.std()
    if std == 0:
        return 0.0
    ratio = float(pnl.mean() / std)
    if periods_per_year:
        ratio *= float(np.sqrt(periods_per_year))
    return ratio


def max_drawdown(equity: np.ndarray) -> float:
    running_max = np.maximum.accumulate(equity)
    drawdown = equity - running_max
    return float(drawdown.min())


def turnover(fill_sizes: np.ndarray) -> float:
    """Total traded notional-units (sum of absolute fill sizes) — the
    denominator that makes a cost-sensitivity robustness test meaningful."""
    return float(np.abs(fill_sizes).sum())
