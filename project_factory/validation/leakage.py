"""Leakage audit (section 11.4, Gate 2).

Checks every ex-ante feature's `available_at` timestamp against the
frame's decision-time column. Any violation excludes that feature from
the primary backtest per Gate 2 rather than silently trusting it.
"""

from __future__ import annotations

import pandas as pd
from pydantic import BaseModel

from project_factory.data.timestamps import LookaheadError, assert_ex_ante
from project_factory.features.base import FeatureDefinition


class LeakageAuditReport(BaseModel):
    passed: bool
    n_ex_ante_checked: int
    n_ex_post_excluded: int
    violations: list[str]
    unsafe_features: list[str]


def audit_leakage(
    df: pd.DataFrame,
    manifest: list[FeatureDefinition],
    decision_time_column: str,
) -> LeakageAuditReport:
    violations: list[str] = []
    unsafe_features: list[str] = []
    n_checked = 0

    for feature in manifest:
        if not feature.ex_ante:
            continue
        n_checked += 1
        try:
            assert_ex_ante(
                df[feature.available_at],
                df[decision_time_column],
                feature_name=feature.name,
            )
        except LookaheadError as exc:
            violations.append(str(exc))
            unsafe_features.append(feature.name)

    n_ex_post = sum(1 for f in manifest if not f.ex_ante)

    return LeakageAuditReport(
        passed=not violations,
        n_ex_ante_checked=n_checked,
        n_ex_post_excluded=n_ex_post,
        violations=violations,
        unsafe_features=unsafe_features,
    )


def safe_feature_columns(manifest: list[FeatureDefinition], audit: LeakageAuditReport) -> list[str]:
    """Feature names safe to feed into a model: ex-ante and not flagged
    by the audit."""
    return [f.name for f in manifest if f.ex_ante and f.name not in audit.unsafe_features]
