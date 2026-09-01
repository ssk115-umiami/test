"""Model wrapper contract (section 11.3)."""

from __future__ import annotations

from typing import Protocol

import numpy as np
import pandas as pd
from pydantic import BaseModel


class ModelSpec(BaseModel):
    name: str
    task_type: str
    """'regression' or 'classification'."""
    params: dict = {}


class ResearchModel(Protocol):
    def fit(self, X: pd.DataFrame, y: pd.Series) -> "ResearchModel": ...

    def predict(self, X: pd.DataFrame) -> np.ndarray: ...

    def diagnostics(self, X: pd.DataFrame, y: pd.Series) -> dict: ...
