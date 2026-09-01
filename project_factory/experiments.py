"""Experiment tracking (section 12) + the walk-forward experiment runner
that section 25's orchestrator pseudocode calls.

Records are stored as JSONL, one line per experiment — deliberately no
database (section 12: "do not build a database server unless needed").
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import pandas as pd
from pydantic import BaseModel, Field

from project_factory.models.base import ResearchModel
from project_factory.validation.walk_forward import WalkForwardValidator


class ExperimentRecord(BaseModel):
    experiment_id: str
    project_id: str
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    features: list[str]
    model: str
    params: dict = Field(default_factory=dict)
    predictive_metrics: dict = Field(default_factory=dict)
    trading_metrics: dict = Field(default_factory=dict)
    diagnostic_metrics: dict = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


def run_walk_forward_experiment(
    X: pd.DataFrame,
    y: pd.Series,
    timestamps: pd.Series,
    model_factory: Callable[[], ResearchModel],
    validator: WalkForwardValidator,
    project_id: str,
    model_name: str,
    params: dict | None = None,
) -> list[ExperimentRecord]:
    """Fit+evaluate `model_factory()` on every walk-forward fold. Returns
    one ExperimentRecord per fold (not aggregated) so per-fold drift and
    instability are visible rather than averaged away — that's exactly
    what the failure analyzer (Milestone 3) needs."""
    params = params or {}
    splits = validator.split(timestamps)
    if not splits:
        raise ValueError(
            "walk-forward validator produced zero splits — check n_train/n_test "
            "against the length of the data"
        )

    records: list[ExperimentRecord] = []
    for i, split in enumerate(splits):
        X_train, y_train = X.iloc[split.train_idx], y.iloc[split.train_idx]
        X_test, y_test = X.iloc[split.test_idx], y.iloc[split.test_idx]

        model = model_factory()
        model.fit(X_train, y_train)
        test_diagnostics = model.diagnostics(X_test, y_test)

        records.append(
            ExperimentRecord(
                experiment_id=f"{model_name}_fold{i}_{params}",
                project_id=project_id,
                train_start=str(split.train_start),
                train_end=str(split.train_end),
                test_start=str(split.test_start),
                test_end=str(split.test_end),
                features=list(X.columns),
                model=model_name,
                params=params,
                predictive_metrics={
                    k: v for k, v in test_diagnostics.items()
                    if isinstance(v, (int, float)) and k not in {"n"}
                },
                diagnostic_metrics=test_diagnostics,
            )
        )
    return records


def save_experiments(records: list[ExperimentRecord], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for record in records:
            f.write(json.dumps(record.model_dump()) + "\n")


def load_experiments(path: Path) -> list[ExperimentRecord]:
    with path.open() as f:
        return [ExperimentRecord.model_validate(json.loads(line)) for line in f if line.strip()]
