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


def _standard_result(
    equity: np.ndarray,
    pnl: np.ndarray,
    inventory: np.ndarray,
    turnover_amount: float,
    fill_rate: float,
    n_fills: int,
) -> dict:
    """The one standard result shape every Strategy.evaluate() should
    return (see trading/base.py's Strategy protocol). This is what makes
    reporting/memo.py's figures/tables archetype-agnostic: it looks for
    these exact keys (total_pnl, sharpe, max_drawdown, fill_rate,
    turnover, equity_curve, inventory_series, ...) regardless of whether
    the "inventory" is quoting inventory (market making) or a directional
    position (power spread trading) — same accounting shape, different
    economic meaning of the underlying position and how equity/pnl were
    computed (see the two assemble_* functions below)."""
    equity = np.asarray(equity, dtype=float)
    pnl = np.asarray(pnl, dtype=float)
    inventory = np.asarray(inventory, dtype=float)
    return {
        "total_pnl": float(equity[-1] - equity[0]) if len(equity) else 0.0,
        "sharpe": sharpe_ratio(pnl),
        "max_drawdown": max_drawdown(equity),
        "fill_rate": fill_rate,
        "n_fills": n_fills,
        "turnover": turnover_amount,
        "avg_inventory": float(np.mean(inventory)) if len(inventory) else 0.0,
        "max_abs_inventory": float(np.max(np.abs(inventory))) if len(inventory) else 0.0,
        "final_inventory": float(inventory[-1]) if len(inventory) else 0.0,
        "equity_curve": equity.tolist(),
        "pnl_series": pnl.tolist(),
        "inventory_series": inventory.tolist(),
    }


def assemble_trading_result(
    cash: np.ndarray,
    inventory: np.ndarray,
    mid_price: np.ndarray,
    fill_sizes: np.ndarray,
    fill_rate: float,
    n_fills: int,
) -> dict:
    """Mark-to-market accounting for a continuously-held inventory
    (used by MarketMakingStrategy): equity = cash + inventory * price,
    PnL is the equity change each step."""
    equity = compute_equity_curve(cash, inventory, mid_price)
    pnl = compute_pnl_series(equity)
    return _standard_result(equity, pnl, inventory, turnover(fill_sizes), fill_rate, n_fills)


def assemble_periodic_trading_result(
    position: np.ndarray,
    period_pnl: np.ndarray,
    traded_notional: np.ndarray,
    fill_rate: float,
    n_fills: int,
) -> dict:
    """Periodic-settlement accounting for a strategy that takes a fresh
    position each period to bet on that same period's realized outcome
    (used by NoTradeSizingStrategy) rather than continuously holding
    inventory marked to a price series — there is no meaningful single
    "price" to mark a power-spread position against between periods, so
    PnL is simply position * that period's realized outcome, and equity
    is its cumulative sum. Same output shape as assemble_trading_result;
    deliberately different mechanics because market making and periodic
    signal-based trading are genuinely different market structures."""
    period_pnl = np.asarray(period_pnl, dtype=float)
    equity = np.cumsum(period_pnl)
    return _standard_result(
        equity, period_pnl, position, float(np.abs(traded_notional).sum()), fill_rate, n_fills
    )
