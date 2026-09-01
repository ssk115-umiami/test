"""Ex-ante timing enforcement (section 3.7, section 11.1).

`assert_ex_ante` is the one function every archetype's feature builder
and every leakage audit ultimately calls: it is the actual mechanism
behind "strictly_ex_ante" in DataSpec.timestamp_policy, not just a label
in a YAML file.
"""

from __future__ import annotations

import pandas as pd


class LookaheadError(ValueError):
    """Raised when a feature's available_at timestamp is after the
    decision timestamp it would be used to predict at."""


def assert_ex_ante(
    available_at: pd.Series,
    decision_time: pd.Series,
    feature_name: str = "<feature>",
) -> None:
    """Raise LookaheadError if any row's feature would not actually have
    been known at decision time. Equal timestamps are allowed (the
    feature becomes known exactly when the decision is made) — callers
    that need a strict margin should pass a shifted decision_time."""
    if len(available_at) != len(decision_time):
        raise ValueError("available_at and decision_time must be the same length")

    available_at = pd.to_datetime(available_at)
    decision_time = pd.to_datetime(decision_time)
    violations = available_at > decision_time
    n_violations = int(violations.sum())
    if n_violations:
        first_idx = violations.idxmax()
        raise LookaheadError(
            f"{feature_name!r}: {n_violations} row(s) have available_at after "
            f"decision_time (first offending index {first_idx}: "
            f"available_at={available_at.loc[first_idx]}, "
            f"decision_time={decision_time.loc[first_idx]})"
        )


def shift_available_at(timestamps: pd.Series, publication_lag: pd.Timedelta) -> pd.Series:
    """Helper for sources with a known publication lag (e.g. a weather
    forecast issued 6 hours before the hour it describes): returns the
    timestamp at which the value is actually knowable."""
    return pd.to_datetime(timestamps) + publication_lag
