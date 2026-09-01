"""Wires the real (network-dependent, unverified — see its module
docstring) NYISO adapter, a synthetic same-schema stand-in, the power
feature builder, the no-trade/sizing strategy, and the (unshifted,
same-row) target for Archetype A into the registry.

This archetype is the deliberate architecture-generalization test:
outside of these registrations, nothing in orchestrator.py, the model
factory, the walk-forward validator, the leakage auditor, or the
reporter needed to change to support it — see IMPLEMENTATION_STATUS.md
for the short list of what genuinely *did* need to change (a `task_type`
already-existing parameter, and factoring the trading-result assembly
into a shared shape with archetype-specific PnL mechanics).
"""

from __future__ import annotations

import pandas as pd

from project_factory import registry
from project_factory.data.adapters.nyiso import NyisoPowerDataAdapter
from project_factory.data.adapters.synthetic_power import SyntheticPowerDataAdapter
from project_factory.features.power import PowerFeatureBuilder
from project_factory.features.power import build_target as _build_power_target
from project_factory.schemas import Archetype
from project_factory.trading.no_trade_sizing import NoTradeSizingStrategy


def _target_builder(df: pd.DataFrame) -> pd.Series:
    return _build_power_target(df)


def register() -> None:
    registry.register_data_adapter(Archetype.POWER_DA_RT, NyisoPowerDataAdapter)
    registry.register_synthetic_data_adapter(Archetype.POWER_DA_RT, SyntheticPowerDataAdapter)
    registry.register_feature_builder(Archetype.POWER_DA_RT, PowerFeatureBuilder)
    registry.register_strategy(Archetype.POWER_DA_RT, NoTradeSizingStrategy)
    registry.register_target_builder(Archetype.POWER_DA_RT, _target_builder)
    registry.register_task_type(Archetype.POWER_DA_RT, "regression")
