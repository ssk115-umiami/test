"""Trading / decision layer (section 11.5).

base.py: Strategy protocol. signals.py: MarketMakingStrategy (the
section-6 Archetype B reservation-price formula r_t = m_t + alpha*mu_hat_t
- gamma*q_t; alpha=0 reproduces the no-alpha baseline). costs.py: fees.
inventory.py: clipping + the -gamma*q_t skew term. pnl.py: equity/PnL/
Sharpe/drawdown/turnover from a cash+inventory path. execution/
fill_simulator.py: ProbabilisticFillSimulator (fill probability decays
with distance from the touch; latency_ticks widens that distance).

Archetype-specific (Archetype B / predictive market making) — a
different archetype's trading layer (e.g. power's sizing/no-trade rule)
would get its own Strategy implementation reusing costs.py/pnl.py.
"""
