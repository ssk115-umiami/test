from pathlib import Path

import numpy as np
import pandas as pd

from project_factory.experiments import load_experiments, run_walk_forward_experiment, save_experiments
from project_factory.models.linear import RidgeModel
from project_factory.validation.walk_forward import WalkForwardValidator


def _synthetic_series(n=200, seed=0):
    rng = np.random.default_rng(seed)
    timestamps = pd.Series(pd.date_range("2024-01-01", periods=n, freq="h"))
    X = pd.DataFrame({"x1": rng.normal(size=n), "x2": rng.normal(size=n)})
    y = 2.0 * X["x1"] + rng.normal(scale=0.2, size=n)
    return X, y, timestamps


def test_run_walk_forward_experiment_produces_one_record_per_fold():
    X, y, timestamps = _synthetic_series()
    validator = WalkForwardValidator(n_train=50, n_test=25)
    records = run_walk_forward_experiment(
        X, y, timestamps,
        model_factory=lambda: RidgeModel(alpha=1.0),
        validator=validator,
        project_id="test_project",
        model_name="ridge",
        params={"alpha": 1.0},
    )

    expected_folds = len(validator.split(timestamps))
    assert len(records) == expected_folds
    assert all(r.project_id == "test_project" for r in records)
    assert all(r.model == "ridge" for r in records)
    assert all("rmse" in r.predictive_metrics for r in records)

    # folds are chronological and non-overlapping (test windows shouldn't repeat)
    test_starts = [r.test_start for r in records]
    assert test_starts == sorted(test_starts)
    assert len(set(test_starts)) == len(test_starts)


def test_run_walk_forward_experiment_raises_on_insufficient_data():
    X, y, timestamps = _synthetic_series(n=10)
    validator = WalkForwardValidator(n_train=50, n_test=25)
    try:
        run_walk_forward_experiment(
            X, y, timestamps,
            model_factory=lambda: RidgeModel(),
            validator=validator,
            project_id="p",
            model_name="ridge",
        )
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_save_and_load_experiments_round_trip(tmp_path: Path):
    X, y, timestamps = _synthetic_series()
    validator = WalkForwardValidator(n_train=50, n_test=25)
    records = run_walk_forward_experiment(
        X, y, timestamps,
        model_factory=lambda: RidgeModel(alpha=2.0),
        validator=validator,
        project_id="p",
        model_name="ridge",
        params={"alpha": 2.0},
    )

    path = tmp_path / "experiments.jsonl"
    save_experiments(records, path)
    reloaded = load_experiments(path)

    assert reloaded == records
