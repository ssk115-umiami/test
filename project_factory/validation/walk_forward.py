"""Chronological walk-forward validation (section 11.4, Gate 4).

Random train/test splitting is prohibited for time-series research
(section 14, Gate 4) unless a specific argument justifies it — this
validator makes the correct thing the only thing: splits are always
built by walking forward through sorted timestamps, train always
strictly precedes test, and windows never overlap.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class WalkForwardSplit:
    train_idx: np.ndarray
    test_idx: np.ndarray
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp


class WalkForwardValidator:
    """Row-count based walk-forward splitter (row counts, not calendar
    windows, so the same validator works whether rows are hourly power
    prices or subsecond order-book events).

    expanding=False: rolling window of exactly `n_train` rows.
    expanding=True: training window grows from index 0 each fold
    (section 13's "change training window" robustness knob controls this).
    """

    def __init__(self, n_train: int, n_test: int, step: int | None = None, expanding: bool = False):
        if n_train <= 0 or n_test <= 0:
            raise ValueError("n_train and n_test must be positive")
        self.n_train = n_train
        self.n_test = n_test
        self.step = step or n_test
        self.expanding = expanding

    def split(self, timestamps: pd.Series) -> list[WalkForwardSplit]:
        ts = pd.to_datetime(pd.Series(timestamps).reset_index(drop=True))
        if not ts.is_monotonic_increasing:
            raise ValueError("timestamps must be sorted ascending before walk-forward splitting")

        n = len(ts)
        splits: list[WalkForwardSplit] = []
        train_start_pos = 0
        while True:
            train_end_pos = train_start_pos + self.n_train  # exclusive
            if train_end_pos >= n:
                break
            test_end_pos = min(train_end_pos + self.n_test, n)

            train_idx = np.arange(0 if self.expanding else train_start_pos, train_end_pos)
            test_idx = np.arange(train_end_pos, test_end_pos)
            if len(test_idx) == 0:
                break

            splits.append(
                WalkForwardSplit(
                    train_idx=train_idx,
                    test_idx=test_idx,
                    train_start=ts.iloc[train_idx[0]],
                    train_end=ts.iloc[train_idx[-1]],
                    test_start=ts.iloc[test_idx[0]],
                    test_end=ts.iloc[test_idx[-1]],
                )
            )
            train_start_pos += self.step

        return splits
