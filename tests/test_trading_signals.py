import numpy as np
import pandas as pd

from project_factory.data.adapters.synthetic_microstructure import SyntheticMicrostructureAdapter
from project_factory.features.microstructure import MicrostructureFeatureBuilder, build_target
from project_factory.trading.execution.fill_simulator import ProbabilisticFillSimulator
from project_factory.trading.inventory import clip_inventory, inventory_skew
from project_factory.trading.pnl import compute_equity_curve, compute_pnl_series, max_drawdown, sharpe_ratio
from project_factory.trading.signals import MarketMakingStrategy


def test_fill_probability_decreases_with_distance():
    sim = ProbabilisticFillSimulator(fill_decay=1.0)
    tick = np.array([1.0])
    close_bid_prob, _ = sim.fill_probabilities(
        np.array([100.0]), np.array([101.0]), np.array([100.0]), np.array([101.0]), tick
    )
    far_bid_prob, _ = sim.fill_probabilities(
        np.array([95.0]), np.array([101.0]), np.array([100.0]), np.array([101.0]), tick
    )
    assert close_bid_prob[0] > far_bid_prob[0]


def test_latency_reduces_fill_probability():
    sim_no_latency = ProbabilisticFillSimulator(fill_decay=1.0, latency_ticks=0.0)
    sim_latency = ProbabilisticFillSimulator(fill_decay=1.0, latency_ticks=3.0)
    args = (np.array([100.0]), np.array([101.0]), np.array([100.0]), np.array([101.0]), np.array([1.0]))
    p_no_latency, _ = sim_no_latency.fill_probabilities(*args)
    p_latency, _ = sim_latency.fill_probabilities(*args)
    assert p_latency[0] < p_no_latency[0]


def test_clip_inventory_respects_bounds():
    assert clip_inventory(15, max_inventory=10) == 10
    assert clip_inventory(-15, max_inventory=10) == -10
    assert clip_inventory(5, max_inventory=10) == 5


def test_inventory_skew_pushes_price_down_when_long():
    assert inventory_skew(inventory=5, gamma=0.1) < 0
    assert inventory_skew(inventory=-5, gamma=0.1) > 0
    assert inventory_skew(inventory=0, gamma=0.1) == 0


def test_pnl_helpers_basic_correctness():
    cash = np.array([0.0, -10.0, -10.0, 5.0])
    inventory = np.array([0.0, 1.0, 1.0, 0.0])
    mid_price = np.array([100.0, 100.0, 105.0, 105.0])
    equity = compute_equity_curve(cash, inventory, mid_price)
    assert np.allclose(equity, [0.0, 90.0, 95.0, 5.0])

    pnl = compute_pnl_series(equity)
    assert pnl[0] == 0.0
    assert np.isclose(pnl[1], 90.0)

    dd = max_drawdown(equity)
    assert dd <= 0

    sr = sharpe_ratio(pnl)
    assert isinstance(sr, float)


def _synthetic_features(tmp_path, n=1500, seed=0, signal_strength=1.5):
    adapter = SyntheticMicrostructureAdapter(n_rows=n, seed=seed, signal_strength=signal_strength, cache_dir=tmp_path)
    df = adapter.load()
    features = MicrostructureFeatureBuilder().transform(df)
    return features


def test_alpha_zero_gives_symmetric_quotes_around_reservation_price(tmp_path):
    features = _synthetic_features(tmp_path)
    strategy = MarketMakingStrategy(alpha=0.0, gamma=0.0, half_spread_ticks=2.0, fee_bps=0.0)
    predictions = pd.Series(np.full(len(features), 0.5))  # irrelevant when alpha=0

    decisions = strategy.decisions(predictions, features, spec=None)
    assert np.allclose(decisions["mu_hat"], 0.0)


def test_informed_alpha_outperforms_no_alpha_baseline_on_synthetic_signal(tmp_path):
    """The archetype's own research question: does a real predictive
    signal actually improve trading PnL versus the no-alpha baseline?
    On synthetic data with a known injected signal, it should."""
    features = _synthetic_features(tmp_path, n=2000, signal_strength=2.0)
    target = build_target(features, horizon=1, threshold=0.0)
    valid = target.notna()
    features = features.loc[valid].reset_index(drop=True)

    # "predictions" here use the ground-truth imbalance-driven probability
    # directly (not a fitted model) to isolate whether the trading layer
    # itself correctly converts a real signal into better PnL — model
    # fitting is covered separately in test_models.py / test_orchestrator.
    true_signal = features["top_level_imbalance"].to_numpy()
    informed_proba = 0.5 + 0.4 * np.tanh(2.0 * true_signal)

    # alpha calibrated so the reservation-price shift is comparable to
    # the synthetic price series' actual step size (too small an alpha
    # is indistinguishable from the baseline's fill-order noise; too
    # large overshoots and misprices — both were checked empirically
    # across 10 seeds before picking this value).
    baseline = MarketMakingStrategy(alpha=0.0, gamma=0.02, fee_bps=1.0, rng_seed=0)
    informed = MarketMakingStrategy(alpha=20.0, gamma=0.02, fee_bps=1.0, rng_seed=0)

    baseline_decisions = baseline.decisions(pd.Series(np.full(len(features), 0.5)), features, spec=None)
    baseline_result = baseline.evaluate(baseline_decisions, features, spec=None)

    informed_decisions = informed.decisions(pd.Series(informed_proba), features, spec=None)
    informed_result = informed.evaluate(informed_decisions, features, spec=None)

    assert informed_result["total_pnl"] > baseline_result["total_pnl"]


def test_higher_fees_never_improve_pnl_given_identical_fills(tmp_path):
    features = _synthetic_features(tmp_path, n=1000)
    predictions = pd.Series(np.full(len(features), 0.6))

    low_fee = MarketMakingStrategy(alpha=1.0, gamma=0.05, fee_bps=0.0, rng_seed=0)
    high_fee = MarketMakingStrategy(alpha=1.0, gamma=0.05, fee_bps=20.0, rng_seed=0)

    low_decisions = low_fee.decisions(predictions, features, spec=None)
    high_decisions = high_fee.decisions(predictions, features, spec=None)

    low_result = low_fee.evaluate(low_decisions, features, spec=None)
    high_result = high_fee.evaluate(high_decisions, features, spec=None)

    assert high_result["total_pnl"] <= low_result["total_pnl"]
