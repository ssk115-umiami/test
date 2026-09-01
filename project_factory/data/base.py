"""Data adapter contract (section 11.1)."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

import pandas as pd

from project_factory.data.quality import DataQualityReport


class DataAdapter(Protocol):
    def fetch(self, spec) -> Path:
        """Download/cache raw data for this spec, return the local path."""
        ...

    def load(self, spec) -> pd.DataFrame:
        """Load the fetched data into a tidy, timestamp-sorted DataFrame."""
        ...

    def validate(self, df: pd.DataFrame, spec) -> DataQualityReport:
        """Run data-quality checks (see data/quality.py) and return the report."""
        ...
