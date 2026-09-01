"""FailureAnalyzer (section 11.6, section 3.6).

Section 3.6: "A model failure that is deeply understood can be more
impressive than a small improvement in headline Sharpe." This module is
what makes that possible — it's mandatory output, not an optional extra.

Kept as one cohesive class (rather than the section-9 sketch's separate
residuals.py/regime.py/stability.py/feature_ablation.py files): at this
scope splitting five ~20-line methods into five files would be premature
fragmentation, not genuine reuse boundaries. Revisit if a method grows
enough to need its own tests/config independent of the others.
"""

from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd

from project_factory.models.base import ResearchModel
from project_factory.validation.walk_forward import WalkForwardValidator


class FailureAnalyzer:
    def largest_errors(
        self,
        y_true: pd.Series,
        y_pred: np.ndarray,
        timestamps: pd.Series,
        n: int = 10,
    ) -> pd.DataFrame:
        """Rows with the largest |y_true - y_pred| — for a classifier,
        y_pred should be the predicted probability, so this surfaces the
        most confidently-wrong predictions, not just misclassifications."""
        errors = np.abs(np.asarray(y_true, dtype=float) - np.asarray(y_pred, dtype=float))
        df = pd.DataFrame({"timestamp": timestamps.to_numpy(), "y_true": y_true, "y_pred": y_pred, "abs_error": errors})
        return df.sort_values("abs_error", ascending=False).head(n).reset_index(drop=True)

    def largest_drawdowns(self, equity_curve: np.ndarray, timestamps: pd.Series | None = None, n: int = 5) -> pd.DataFrame:
        """Top-n peak-to-trough drawdown episodes: (peak_idx, trough_idx,
        depth, recovery_idx or None if not yet recovered by series end)."""
        equity = np.asarray(equity_curve, dtype=float)
        running_max = np.maximum.accumulate(equity)
        drawdown = equity - running_max

        episodes = []
        in_drawdown = False
        peak_idx = 0
        for i in range(len(equity)):
            if drawdown[i] < 0 and not in_drawdown:
                in_drawdown = True
                peak_idx = i - 1 if i > 0 else 0
            if in_drawdown and (drawdown[i] == 0 or i == len(equity) - 1):
                trough_idx = int(np.argmin(equity[peak_idx : i + 1]) + peak_idx)
                episodes.append(
                    {
                        "peak_idx": peak_idx,
                        "trough_idx": trough_idx,
                        "recovery_idx": i if drawdown[i] == 0 else None,
                        "depth": float(equity[trough_idx] - equity[peak_idx]),
                    }
                )
                in_drawdown = False

        df = pd.DataFrame(episodes).sort_values("depth").head(n).reset_index(drop=True)
        if timestamps is not None and not df.empty:
            ts = timestamps.reset_index(drop=True)
            df["peak_time"] = df["peak_idx"].map(ts)
            df["trough_time"] = df["trough_idx"].map(ts)
        return df

    def regime_breakdown(
        self,
        y_true: pd.Series,
        y_pred: np.ndarray,
        regime_labels: pd.Series,
        metric_fn: Callable[[pd.Series, np.ndarray], dict],
    ) -> pd.DataFrame:
        """Apply metric_fn (e.g. models.diagnostics.classification_metrics
        or regression_metrics) separately within each regime label, so a
        model that looks fine on average but fails in one regime is
        visible rather than averaged away."""
        rows = []
        y_pred = np.asarray(y_pred)
        for label, idx in pd.Series(regime_labels.to_numpy()).groupby(regime_labels.to_numpy()).groups.items():
            idx = np.asarray(list(idx))
            metrics = metric_fn(y_true.iloc[idx], y_pred[idx])
            rows.append({"regime": label, "n": len(idx), **metrics})
        return pd.DataFrame(rows).sort_values("regime").reset_index(drop=True)

    def parameter_stability(self, fold_diagnostics: list[dict], param_key: str = "coefficients") -> pd.DataFrame:
        """Track a coefficient (or any scalar diagnostic) across
        walk-forward folds — large swings indicate an unstable model
        that a single full-sample fit would have hidden."""
        rows = []
        for i, diag in enumerate(fold_diagnostics):
            value = diag.get(param_key)
            if isinstance(value, dict):
                rows.append({"fold": i, **value})
            else:
                rows.append({"fold": i, param_key: value})
        df = pd.DataFrame(rows)
        if len(df) > 1:
            numeric_cols = df.select_dtypes(include=[float, int]).columns.drop("fold", errors="ignore")
            for col in numeric_cols:
                df[f"{col}_pct_change"] = df[col].pct_change()
        return df

    def feature_ablation(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        timestamps: pd.Series,
        model_factory: Callable[[], ResearchModel],
        validator: WalkForwardValidator,
        metric_key: str = "rmse",
    ) -> pd.DataFrame:
        """Drop each feature one at a time, rerun walk-forward, compare
        the average test metric to the full-feature-set baseline. A
        feature whose removal barely changes the metric is dead weight
        (or worse, a leakage artifact propping up the headline number)."""
        from project_factory.experiments import run_walk_forward_experiment

        def _avg_metric(features: list[str]) -> float:
            records = run_walk_forward_experiment(
                X[features], y, timestamps, model_factory, validator,
                project_id="ablation", model_name="ablation",
            )
            values = [r.predictive_metrics[metric_key] for r in records if metric_key in r.predictive_metrics]
            return float(np.mean(values)) if values else float("nan")

        baseline = _avg_metric(list(X.columns))
        rows = [{"dropped_feature": None, metric_key: baseline, "delta_vs_baseline": 0.0}]
        for col in X.columns:
            remaining = [c for c in X.columns if c != col]
            if not remaining:
                continue
            score = _avg_metric(remaining)
            rows.append({"dropped_feature": col, metric_key: score, "delta_vs_baseline": score - baseline})
        return pd.DataFrame(rows)
