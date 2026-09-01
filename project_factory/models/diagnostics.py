"""Standard predictive metrics + linear-model diagnostics (section 11.3,
section 15 — regularization/conditioning as an interview-defense topic).

Kept as plain functions rather than methods so both `ResearchModel.diagnostics`
and the failure analyzer (Milestone 3) can call the same code.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    log_loss,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
    roc_auc_score,
)


def regression_metrics(y_true: pd.Series, y_pred: np.ndarray) -> dict:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    return {
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "r2": float(r2_score(y_true, y_pred)) if len(set(y_true)) > 1 else float("nan"),
        "n": len(y_true),
    }


def classification_metrics(y_true: pd.Series, y_proba: np.ndarray) -> dict:
    y_true = np.asarray(y_true)
    y_proba = np.asarray(y_proba, dtype=float)
    y_pred = (y_proba >= 0.5).astype(int)
    metrics = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "n": len(y_true),
    }
    if len(set(y_true)) > 1:
        metrics["auc"] = float(roc_auc_score(y_true, y_proba))
        eps = 1e-9
        clipped = np.clip(y_proba, eps, 1 - eps)
        metrics["log_loss"] = float(log_loss(y_true, clipped))
    else:
        metrics["auc"] = float("nan")
        metrics["log_loss"] = float("nan")
    return metrics


def condition_number(X: pd.DataFrame | np.ndarray) -> float:
    """Condition number of the (intercept-augmented) design matrix — the
    standard interview-defense number for "is multicollinearity a
    problem here" (section 15)."""
    arr = np.asarray(X, dtype=float)
    if arr.ndim == 1:
        arr = arr.reshape(-1, 1)
    augmented = np.column_stack([np.ones(len(arr)), arr])
    singular_values = np.linalg.svd(augmented, compute_uv=False)
    if singular_values.min() == 0:
        return float("inf")
    return float(singular_values.max() / singular_values.min())


def coefficient_table(feature_names: list[str], coefficients: np.ndarray) -> dict[str, float]:
    return {name: float(coef) for name, coef in zip(feature_names, coefficients)}
