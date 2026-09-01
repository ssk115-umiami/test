"""Model-name -> ResearchModel factory.

The archetype YAML configs (configs/archetypes/*.yaml) name models as
plain strings (e.g. "ridge", "gradient_boosted_tree") in their model
ladder. This is the one place that turns those names into actual
instances, using the reusable wrappers from models/linear.py and
models/tree.py — scoped to the names Milestones 3/4 actually use rather
than every name across all 7 archetype configs (several of those, like
"black_scholes_static_vol" or "no_alpha_symmetric_market_maker", are
pricing/strategy baselines rather than ResearchModel-shaped predictive
models, and don't belong here).
"""

from __future__ import annotations

from typing import Callable

from project_factory.models.base import ResearchModel
from project_factory.models.linear import LogisticModel, NaiveBaselineModel, OLSModel, RidgeModel
from project_factory.models.tree import GradientBoostedTreeModel

_REGRESSION_BUILDERS: dict[str, Callable[[dict], ResearchModel]] = {
    "naive_zero_spread": lambda p: NaiveBaselineModel(strategy="zero"),
    "seasonal_naive": lambda p: NaiveBaselineModel(strategy="last_value"),
    "naive_seasonal": lambda p: NaiveBaselineModel(strategy="last_value"),
    "naive_buy_and_hold": lambda p: NaiveBaselineModel(strategy="last_value"),
    "ols": lambda p: OLSModel(),
    "ols_cross_sectional": lambda p: OLSModel(),
    "ridge": lambda p: RidgeModel(alpha=p.get("alpha", 1.0)),
    "gradient_boosted_tree": lambda p: GradientBoostedTreeModel(
        task_type="regression", **{k: v for k, v in p.items() if k != "alpha"}
    ),
}

_CLASSIFICATION_BUILDERS: dict[str, Callable[[dict], ResearchModel]] = {
    "logistic_regression": lambda p: LogisticModel(C=p.get("C", 1.0)),
    "ridge_or_regularized_logistic": lambda p: LogisticModel(C=p.get("C", 1.0)),
    "gradient_boosted_tree": lambda p: GradientBoostedTreeModel(task_type="classification", **p),
}

_BUILDERS_BY_TASK = {"regression": _REGRESSION_BUILDERS, "classification": _CLASSIFICATION_BUILDERS}


def build_model(name: str, task_type: str, params: dict | None = None) -> ResearchModel:
    params = params or {}
    try:
        builders = _BUILDERS_BY_TASK[task_type]
    except KeyError as exc:
        raise ValueError(f"unknown task_type {task_type!r}, must be 'regression' or 'classification'") from exc
    try:
        return builders[name](params)
    except KeyError as exc:
        raise ValueError(
            f"no {task_type} model builder registered for {name!r}; known names: {sorted(builders)}"
        ) from exc
