import numpy as np
import pandas as pd
import pytest

from project_factory.models.diagnostics import condition_number
from project_factory.models.linear import LogisticModel, NaiveBaselineModel, OLSModel, RidgeModel
from project_factory.models.tree import GradientBoostedTreeModel


def _linear_regression_data(n=200, seed=0):
    rng = np.random.default_rng(seed)
    X = pd.DataFrame({"x1": rng.normal(size=n), "x2": rng.normal(size=n)})
    y = 3.0 * X["x1"] - 2.0 * X["x2"] + rng.normal(scale=0.1, size=n)
    return X, y


def _binary_classification_data(n=300, seed=0):
    rng = np.random.default_rng(seed)
    X = pd.DataFrame({"x1": rng.normal(size=n), "x2": rng.normal(size=n)})
    logits = 2.0 * X["x1"] - 1.5 * X["x2"]
    proba = 1 / (1 + np.exp(-logits))
    y = pd.Series((rng.uniform(size=n) < proba).astype(int))
    return X, y


def test_naive_baseline_mean_strategy():
    X, y = _linear_regression_data()
    model = NaiveBaselineModel(strategy="mean").fit(X, y)
    preds = model.predict(X)
    assert np.allclose(preds, y.mean())


def test_naive_baseline_last_value_strategy():
    X, y = _linear_regression_data()
    model = NaiveBaselineModel(strategy="last_value").fit(X, y)
    assert model.predict(X)[0] == y.iloc[-1]


def test_ols_recovers_known_coefficients():
    X, y = _linear_regression_data(n=2000)
    model = OLSModel().fit(X, y)
    diag = model.diagnostics(X, y)
    assert diag["coefficients"]["x1"] == pytest.approx(3.0, abs=0.1)
    assert diag["coefficients"]["x2"] == pytest.approx(-2.0, abs=0.1)
    assert diag["r2"] > 0.95


def test_ridge_shrinks_coefficients_relative_to_ols():
    X, y = _linear_regression_data(n=500)
    ols = OLSModel().fit(X, y)
    ridge = RidgeModel(alpha=50.0).fit(X, y)

    ols_norm = sum(abs(v) for v in ols.diagnostics(X, y)["coefficients"].values())
    ridge_norm = sum(abs(v) for v in ridge.diagnostics(X, y)["coefficients"].values())
    assert ridge_norm < ols_norm


def test_ridge_alpha_zero_approaches_ols():
    X, y = _linear_regression_data(n=1000)
    ols = OLSModel().fit(X, y)
    ridge = RidgeModel(alpha=1e-6).fit(X, y)

    ols_coef = ols.diagnostics(X, y)["coefficients"]
    ridge_coef = ridge.diagnostics(X, y)["coefficients"]
    for k in ols_coef:
        assert abs(ols_coef[k] - ridge_coef[k]) < 0.05


def test_condition_number_higher_for_collinear_features():
    rng = np.random.default_rng(0)
    n = 200
    x1 = rng.normal(size=n)
    well_conditioned = pd.DataFrame({"x1": x1, "x2": rng.normal(size=n)})
    collinear = pd.DataFrame({"x1": x1, "x2": x1 + rng.normal(scale=1e-3, size=n)})

    assert condition_number(collinear) > condition_number(well_conditioned) * 10


def test_logistic_model_predicts_probabilities_and_metrics():
    X, y = _binary_classification_data()
    model = LogisticModel().fit(X, y)
    proba = model.predict(X)
    assert (proba >= 0).all() and (proba <= 1).all()

    diag = model.diagnostics(X, y)
    assert diag["accuracy"] > 0.6
    assert 0.5 < diag["auc"] <= 1.0


def test_gradient_boosted_regressor_beats_naive_baseline():
    X, y = _linear_regression_data(n=500)
    baseline = NaiveBaselineModel(strategy="mean").fit(X, y)
    gbt = GradientBoostedTreeModel(task_type="regression", n_estimators=50, max_depth=3).fit(X, y)

    baseline_rmse = baseline.diagnostics(X, y)["rmse"]
    gbt_rmse = gbt.diagnostics(X, y)["rmse"]
    assert gbt_rmse < baseline_rmse


def test_gradient_boosted_classifier_reports_feature_importances():
    X, y = _binary_classification_data()
    model = GradientBoostedTreeModel(task_type="classification", n_estimators=30).fit(X, y)
    diag = model.diagnostics(X, y)
    assert set(diag["feature_importances"].keys()) == {"x1", "x2"}
    assert diag["accuracy"] > 0.5
