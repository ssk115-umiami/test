"""Feature contract (section 11.2, section 3.7).

Every feature a project uses must declare when it would actually have
been known (`available_at`) and whether it's legitimately usable as a
predictive input (`ex_ante`) or only as an after-the-fact diagnostic
variable. This is what `validation.leakage.audit_leakage` checks against
decision timestamps, and it is mandatory — section 3.7 calls this
distinction non-negotiable for every time-series / trading project.
"""

from __future__ import annotations

from typing import Protocol

import pandas as pd
from pydantic import BaseModel


class FeatureDefinition(BaseModel):
    name: str
    description: str
    economic_rationale: str
    source_columns: list[str]
    calculation: str
    """Human-readable description of how the feature is computed (not
    executable code) — this is recruiting/audit documentation, the actual
    computation lives in FeatureBuilder.transform."""
    available_at: str
    """Which column in the transformed frame holds the timestamp at which
    this feature's value would actually have been knowable."""
    ex_ante: bool
    """True: legitimately usable as a predictive input. False: an
    ex-post diagnostic variable (section 3.7) — must never enter a
    model's feature matrix, only failure-analysis code."""
    leakage_risk_notes: str = ""


class FeatureBuilder(Protocol):
    def transform(self, df: pd.DataFrame, spec) -> pd.DataFrame:
        """Return df with feature columns added. Must not introduce any
        row that depends on information from after that row's decision
        timestamp for an ex_ante feature."""
        ...

    def feature_manifest(self) -> list[FeatureDefinition]:
        """One FeatureDefinition per column this builder adds."""
        ...


def ex_ante_feature_names(manifest: list[FeatureDefinition]) -> list[str]:
    return [f.name for f in manifest if f.ex_ante]


def ex_post_feature_names(manifest: list[FeatureDefinition]) -> list[str]:
    return [f.name for f in manifest if not f.ex_ante]
