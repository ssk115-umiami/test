import numpy as np
import pandas as pd
import pytest

from project_factory.diagnostics.failure_cases import FailureAnalyzer
from project_factory.models.diagnostics import classification_metrics
from project_factory.models.linear import RidgeModel
from project_factory.validation.walk_forward import WalkForwardValidator


def test_largest_errors_sorted_descending():
    y_true = pd.Series([0.0, 1.0, 0.0, 1.0, 0.0])
    y_pred = np.array([0.1, 0.2, 0.9, 0.6, 0.05])
    timestamps = pd.Series(pd.date_range("2024-01-01", periods=5, freq="h"))

    result = FailureAnalyzer().largest_errors(y_true, y_pred, timestamps, n=3)
    assert len(result) == 3
    assert result["abs_error"].is_monotonic_decreasing
    assert result.iloc[0]["abs_error"] == pytest.approx(0.9)


def test_largest_drawdowns_finds_the_big_dip():
    # equity rises to 10, drops to 2, recovers to 12
    equity = np.array([0, 2, 5, 10, 8, 5, 2, 4, 8, 12])
    result = FailureAnalyzer().largest_drawdowns(equity, n=2)
    assert len(result) >= 1
    worst = result.iloc[0]
    assert worst["depth"] == pytest.approx(2 - 10)


def test_regime_breakdown_groups_by_label():
    y_true = pd.Series([1, 1, 0, 0, 1, 1])
    y_pred = np.array([0.9, 0.8, 0.9, 0.8, 0.1, 0.2])  # bad in "high_vol" regime
    regime = pd.Series(["low_vol", "low_vol", "low_vol", "low_vol", "high_vol", "high_vol"])

    result = FailureAnalyzer().regime_breakdown(y_true, y_pred, regime, classification_metrics)
    assert set(result["regime"]) == {"low_vol", "high_vol"}
    low_vol_acc = result.loc[result["regime"] == "low_vol", "accuracy"].iloc[0]
    high_vol_acc = result.loc[result["regime"] == "high_vol", "accuracy"].iloc[0]
    assert high_vol_acc < low_vol_acc


def test_parameter_stability_tracks_coefficients_across_folds():
    fold_diagnostics = [
        {"coefficients": {"x1": 1.0, "x2": -1.0}},
        {"coefficients": {"x1": 1.5, "x2": -0.5}},
        {"coefficients": {"x1": 3.0, "x2": 0.5}},
    ]
    result = FailureAnalyzer().parameter_stability(fold_diagnostics)
    assert len(result) == 3
    assert "x1_pct_change" in result.columns
    assert result["x1_pct_change"].iloc[1] == pytest.approx(0.5)


def test_feature_ablation_flags_the_informative_feature():
    rng = np.random.default_rng(0)
    n = 400
    x_informative = rng.normal(size=n)
    x_noise = rng.normal(size=n)
    y = 3.0 * x_informative + rng.normal(scale=0.2, size=n)
    X = pd.DataFrame({"x_informative": x_informative, "x_noise": x_noise})
    timestamps = pd.Series(pd.date_range("2024-01-01", periods=n, freq="h"))
    validator = WalkForwardValidator(n_train=150, n_test=50)

    result = FailureAnalyzer().feature_ablation(
        X, pd.Series(y), timestamps, model_factory=lambda: RidgeModel(alpha=0.1), validator=validator
    )

    dropped_informative = result.loc[result["dropped_feature"] == "x_informative", "delta_vs_baseline"].iloc[0]
    dropped_noise = result.loc[result["dropped_feature"] == "x_noise", "delta_vs_baseline"].iloc[0]
    # dropping the informative feature should hurt (increase rmse) far more than dropping noise
    assert dropped_informative > dropped_noise
