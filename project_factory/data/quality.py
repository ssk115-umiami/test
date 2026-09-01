"""Data quality report (section 11.1's DataQualityReport).

A small, honest checklist run right after a DataAdapter loads a frame —
this is what Gate 9 ("no fake claims") leans on: you can't claim a
dataset is clean without having actually looked at it.
"""

from __future__ import annotations

import pandas as pd
from pydantic import BaseModel, Field


class DataQualityReport(BaseModel):
    n_rows: int
    n_columns: int
    timestamp_column: str
    is_sorted_ascending: bool
    has_duplicate_timestamps: bool
    n_duplicate_timestamps: int
    missing_fraction_by_column: dict[str, float] = Field(default_factory=dict)
    min_timestamp: str | None = None
    max_timestamp: str | None = None
    gaps_detected: bool = False
    notes: list[str] = Field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return (
            self.is_sorted_ascending
            and not self.has_duplicate_timestamps
            and all(frac < 0.2 for frac in self.missing_fraction_by_column.values())
        )


def build_quality_report(
    df: pd.DataFrame,
    timestamp_column: str,
    expected_frequency: pd.Timedelta | None = None,
) -> DataQualityReport:
    if timestamp_column not in df.columns:
        raise ValueError(f"timestamp_column {timestamp_column!r} not in dataframe columns")

    ts = pd.to_datetime(df[timestamp_column])
    is_sorted = bool(ts.is_monotonic_increasing)
    dupes = int(ts.duplicated().sum())

    missing_frac = {col: float(df[col].isna().mean()) for col in df.columns}

    gaps_detected = False
    notes: list[str] = []
    if expected_frequency is not None and len(ts) > 1:
        sorted_ts = ts.sort_values()
        diffs = sorted_ts.diff().dropna()
        gaps_detected = bool((diffs > expected_frequency * 1.5).any())
        if gaps_detected:
            notes.append(
                f"detected {(diffs > expected_frequency * 1.5).sum()} gap(s) larger than "
                f"1.5x expected frequency ({expected_frequency})"
            )

    if dupes:
        notes.append(f"{dupes} duplicate timestamp(s) found in {timestamp_column!r}")
    if not is_sorted:
        notes.append(f"{timestamp_column!r} is not monotonically increasing")

    return DataQualityReport(
        n_rows=len(df),
        n_columns=len(df.columns),
        timestamp_column=timestamp_column,
        is_sorted_ascending=is_sorted,
        has_duplicate_timestamps=dupes > 0,
        n_duplicate_timestamps=dupes,
        missing_fraction_by_column=missing_frac,
        min_timestamp=str(ts.min()) if len(ts) else None,
        max_timestamp=str(ts.max()) if len(ts) else None,
        gaps_detected=gaps_detected,
        notes=notes,
    )
