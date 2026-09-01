"""Transaction costs (section 6 Archetype B: fees are a mandatory
robustness dimension, not an optional add-on)."""

from __future__ import annotations

import numpy as np


def fee_amount(notional: np.ndarray | float, fee_bps: float) -> np.ndarray | float:
    return np.abs(notional) * (fee_bps / 10_000.0)
