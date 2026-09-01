"""Section 3.4 step 4: one strong nonlinear benchmark.

Uses sklearn's gradient boosting (no extra dependency) so the baseline
model ladder works out of the box; archetypes that want xgboost/lightgbm
can swap this via the `boosted` optional dependency group without
touching the ResearchModel contract.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor

from project_factory.models.diagnostics import classification_metrics, regression_metrics


class GradientBoostedTreeModel:
    def __init__(self, task_type: str = "regression", **params):
        if task_type not in {"regression", "classification"}:
            raise ValueError(f"unknown task_type: {task_type!r}")
        self.task_type = task_type
        cls = GradientBoostingRegressor if task_type == "regression" else GradientBoostingClassifier
        self._model = cls(**params)
        self._feature_names: list[str] = []

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "GradientBoostedTreeModel":
        self._feature_names = list(X.columns)
        self._model.fit(X, y)
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if self.task_type == "classification":
            return self._model.predict_proba(X)[:, 1]
        return self._model.predict(X)

    def diagnostics(self, X: pd.DataFrame, y: pd.Series) -> dict:
        preds = self.predict(X)
        importances = dict(zip(self._feature_names, self._model.feature_importances_.tolist()))
        metrics = (
            classification_metrics(y, preds)
            if self.task_type == "classification"
            else regression_metrics(y, preds)
        )
        return {"feature_importances": importances, **metrics}
