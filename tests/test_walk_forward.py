import pandas as pd
import pytest

from project_factory.validation.walk_forward import WalkForwardValidator


def _timestamps(n: int) -> pd.Series:
    return pd.Series(pd.date_range("2024-01-01", periods=n, freq="h"))


def test_splits_are_chronological_and_non_overlapping():
    ts = _timestamps(100)
    validator = WalkForwardValidator(n_train=20, n_test=10)
    splits = validator.split(ts)

    assert len(splits) > 0
    for split in splits:
        assert split.train_end <= split.test_start
        assert max(split.train_idx) < min(split.test_idx)
        # no overlap between this split's train and test index sets
        assert set(split.train_idx).isdisjoint(set(split.test_idx))


def test_splits_walk_forward_in_order():
    ts = _timestamps(100)
    validator = WalkForwardValidator(n_train=20, n_test=10)
    splits = validator.split(ts)

    for prev, nxt in zip(splits, splits[1:]):
        assert nxt.test_start > prev.test_start
        assert nxt.train_start >= prev.train_start


def test_expanding_window_grows_train_set():
    ts = _timestamps(100)
    validator = WalkForwardValidator(n_train=20, n_test=10, expanding=True)
    splits = validator.split(ts)

    sizes = [len(s.train_idx) for s in splits]
    assert sizes == sorted(sizes)
    assert sizes[0] < sizes[-1]


def test_rolling_window_keeps_train_set_size_constant():
    ts = _timestamps(100)
    validator = WalkForwardValidator(n_train=20, n_test=10, expanding=False)
    splits = validator.split(ts)

    assert all(len(s.train_idx) == 20 for s in splits)


def test_unsorted_timestamps_raises():
    ts = pd.Series(pd.date_range("2024-01-01", periods=20, freq="h"))
    shuffled = ts.sample(frac=1.0, random_state=0).reset_index(drop=True)
    validator = WalkForwardValidator(n_train=5, n_test=5)
    with pytest.raises(ValueError):
        validator.split(shuffled)


def test_too_little_data_returns_no_splits():
    ts = _timestamps(5)
    validator = WalkForwardValidator(n_train=20, n_test=10)
    assert validator.split(ts) == []
