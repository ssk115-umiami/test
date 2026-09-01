"""Wires the real (network-dependent) pieces for Archetype B into the
registry: BybitPublicDataAdapter (see its module docstring for the
verification-status caveats), MicrostructureFeatureBuilder,
MarketMakingStrategy, and a target builder (binary next-`HORIZON`-row
mid-price direction).

Importing project_factory.archetypes (this module's package) is what
makes Archetype.PREDICTIVE_MARKET_MAKING show up in
registry.IMPLEMENTED_ARCHETYPES, which is what lets `qpf run`/`qpf
report` work for it instead of erroring.
"""

from __future__ import annotations

import pandas as pd

from project_factory import registry
from project_factory.data.adapters.bybit_l2 import BybitPublicDataAdapter
from project_factory.data.adapters.synthetic_microstructure import SyntheticMicrostructureAdapter
from project_factory.features.microstructure import MicrostructureFeatureBuilder, build_target
from project_factory.schemas import Archetype
from project_factory.trading.signals import MarketMakingStrategy

PREDICTION_HORIZON = 5
"""Rows ahead the target looks — i.e. predicting whether mid_price is
higher `PREDICTION_HORIZON` snapshots from now. A snapshot-count horizon
(not a fixed time window) so it's meaningful regardless of the actual
data cadence."""


def _target_builder(df: pd.DataFrame) -> pd.Series:
    return build_target(df, horizon=PREDICTION_HORIZON, threshold=0.0)


def register() -> None:
    registry.register_data_adapter(Archetype.PREDICTIVE_MARKET_MAKING, BybitPublicDataAdapter)
    registry.register_synthetic_data_adapter(Archetype.PREDICTIVE_MARKET_MAKING, SyntheticMicrostructureAdapter)
    registry.register_feature_builder(Archetype.PREDICTIVE_MARKET_MAKING, MicrostructureFeatureBuilder)
    registry.register_strategy(Archetype.PREDICTIVE_MARKET_MAKING, MarketMakingStrategy)
    registry.register_target_builder(Archetype.PREDICTIVE_MARKET_MAKING, _target_builder)
