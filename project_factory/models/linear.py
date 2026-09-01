"""Model ladder step 1-3 (section 3.4): naive baseline, OLS, regularized
linear/logistic. Each wrapper's `diagnostics()` returns the numbers a
candidate should be able to defend from first principles (section 15):
coefficients, condition number, and predictive metrics.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression, LogisticRegression, Ridge

from project_factory.models.diagnostics import (
    classification_metrics,
    coefficient_table,
    condition_number,
    regression_metrics,
)


class NaiveBaselineModel:
    """Section 3.4 step 1: naive/economic baseline. `strategy` controls
    what "naive" means: 'zero' (predict 0 — e.g. no spread), 'mean'
    (predict the training-set mean), or 'last_value' (predict the most
    recent observed y — a persistence/random-walk baseline)."""

    def __init__(self, strategy: str = "mean"):
        if strategy not in {"zero", "mean", "last_value"}:
            raise ValueError(f"unknown baseline strategy: {strategy!r}")
        self.strategy = strategy
        self._value: float = 0.0

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "NaiveBaselineModel":
        if self.strategy == "zero":
            self._value = 0.0
        elif self.strategy == "mean":
            self._value = float(np.mean(y))
        elif self.strategy == "last_value":
            self._value = float(y.iloc[-1])
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return np.full(len(X), self._value)

    def diagnostics(self, X: pd.DataFrame, y: pd.Series) -> dict:
        preds = self.predict(X)
        return {"strategy": self.strategy, "value": self._value, **regression_metrics(y, preds)}


class OLSModel:
    """Section 3.4 step 2."""

    def __init__(self):
        self._model = LinearRegression()
        self._feature_names: list[str] = []

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "OLSModel":
        self._feature_names = list(X.columns)
        self._model.fit(X, y)
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return self._model.predict(X)

    def diagnostics(self, X: pd.DataFrame, y: pd.Series) -> dict:
        preds = self.predict(X)
        return {
            "coefficients": coefficient_table(self._feature_names, self._model.coef_),
            "intercept": float(self._model.intercept_),
            "condition_number": condition_number(X),
            **regression_metrics(y, preds),
        }


class RidgeModel:
    """Section 3.4 step 3 / section 15's canonical regularization example:
    beta_ridge = (X^T X + lambda I)^-1 X^T y."""

    def __init__(self, alpha: float = 1.0):
        self.alpha = alpha
        self._model = Ridge(alpha=alpha)
        self._feature_names: list[str] = []

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "RidgeModel":
        self._feature_names = list(X.columns)
        self._model.fit(X, y)
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return self._model.predict(X)

    def diagnostics(self, X: pd.DataFrame, y: pd.Series) -> dict:
        preds = self.predict(X)
        return {
            "alpha": self.alpha,
            "coefficients": coefficient_table(self._feature_names, self._model.coef_),
            "intercept": float(self._model.intercept_),
            "condition_number": condition_number(X),
            **regression_metrics(y, preds),
        }


class LogisticModel:
    """Regularized logistic regression (L2 by default — sklearn's
    LogisticRegression is ridge-penalized unless penalty='none')."""

    def __init__(self, C: float = 1.0, penalty: str = "l2"):
        self.C = C
        self.penalty = penalty
        # sklearn >=1.8 deprecates the `penalty` kwarg entirely (warns on
        # any explicit value, including its own default); only pass it
        # through for a non-default choice so the common case stays warning-free
        # on both old and new sklearn versions.
        kwargs = {} if penalty == "l2" else {"penalty": penalty}
        self._model = LogisticRegression(C=C, max_iter=1000, **kwargs)
        self._feature_names: list[str] = []

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "LogisticModel":
        self._feature_names = list(X.columns)
        self._model.fit(X, y)
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Returns predicted probability of the positive class (not the
        thresholded label) so downstream trading/decision code can apply
        its own threshold."""
        return self._model.predict_proba(X)[:, 1]

    def diagnostics(self, X: pd.DataFrame, y: pd.Series) -> dict:
        proba = self.predict(X)
        return {
            "C": self.C,
            "penalty": self.penalty,
            "coefficients": coefficient_table(self._feature_names, self._model.coef_[0]),
            "intercept": float(self._model.intercept_[0]),
            "condition_number": condition_number(X),
            **classification_metrics(y, proba),
        }
