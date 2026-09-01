import numpy as np
import pandas as pd

from project_factory.trading.no_trade_sizing import NoTradeSizingStrategy


def _market_state(n=10):
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=n, freq="h"),
            "da_rt_spread": np.zeros(n),
        }
    )


def test_no_trade_band_zeroes_small_predictions():
    strategy = NoTradeSizingStrategy(no_trade_threshold=2.0, max_position=10.0, size_scale=1.0)
    market = _market_state(5)
    predictions = pd.Series([0.5, -1.0, 1.9, 2.1, -3.0])

    decisions = strategy.decisions(predictions, market)
    assert list(decisions["position_size"] == 0) == [True, True, True, False, False]


def test_position_size_scales_with_prediction_and_caps_at_max():
    strategy = NoTradeSizingStrategy(no_trade_threshold=0.0, max_position=3.0, size_scale=2.0)
    market = _market_state(3)
    predictions = pd.Series([1.0, -1.0, 10.0])

    decisions = strategy.decisions(predictions, market)
    assert decisions["position_size"].tolist() == [2.0, -2.0, 3.0]  # last one capped


def test_evaluate_requires_da_rt_spread_column():
    strategy = NoTradeSizingStrategy()
    market = _market_state(3)
    decisions = strategy.decisions(pd.Series([5.0, 5.0, 5.0]), market)
    bad_realized = market.drop(columns=["da_rt_spread"])
    try:
        strategy.evaluate(decisions, bad_realized)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_positive_position_with_positive_realized_spread_earns_positive_pnl():
    strategy = NoTradeSizingStrategy(no_trade_threshold=0.0, max_position=10.0, size_scale=1.0, fee_bps=0.0)
    n = 5
    market = pd.DataFrame(
        {"timestamp": pd.date_range("2024-01-01", periods=n, freq="h"), "da_rt_spread": np.full(n, 3.0)}
    )
    predictions = pd.Series(np.full(n, 3.0))  # matches realized exactly -> position=3 each period

    decisions = strategy.decisions(predictions, market)
    result = strategy.evaluate(decisions, market)
    assert result["total_pnl"] > 0
    assert result["fill_rate"] == 1.0  # always has an open position


def test_higher_fees_never_improve_pnl_given_identical_positions():
    n = 20
    rng = np.random.default_rng(0)
    market = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=n, freq="h"),
            "da_rt_spread": rng.normal(size=n),
        }
    )
    predictions = pd.Series(rng.normal(size=n))

    low_fee = NoTradeSizingStrategy(no_trade_threshold=0.0, fee_bps=0.0)
    high_fee = NoTradeSizingStrategy(no_trade_threshold=0.0, fee_bps=50.0)

    low_decisions = low_fee.decisions(predictions, market)
    high_decisions = high_fee.decisions(predictions, market)
    # positions should be identical (fees don't affect sizing) — the point of this test
    assert np.allclose(low_decisions["position_size"], high_decisions["position_size"])

    low_result = low_fee.evaluate(low_decisions, market)
    high_result = high_fee.evaluate(high_decisions, market)
    assert high_result["total_pnl"] <= low_result["total_pnl"]


def test_result_shape_matches_market_making_strategy_keys():
    """Cross-archetype reuse check: reporting/memo.py must be able to
    treat both strategies' evaluate() output identically."""
    from project_factory.trading.signals import MarketMakingStrategy

    strategy = NoTradeSizingStrategy()
    market = _market_state(5)
    decisions = strategy.decisions(pd.Series([0.5] * 5), market)
    power_result = strategy.evaluate(decisions, market)

    expected_keys = {
        "total_pnl", "sharpe", "max_drawdown", "fill_rate", "n_fills", "turnover",
        "avg_inventory", "max_abs_inventory", "final_inventory",
        "equity_curve", "pnl_series", "inventory_series",
    }
    assert expected_keys.issubset(power_result.keys())
    # (MarketMakingStrategy import above just documents which other strategy
    # this shape is shared with; no instance needed for the key-set check.)
    assert MarketMakingStrategy is not None
