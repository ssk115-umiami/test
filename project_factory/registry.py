"""Archetype registry (section 9).

Loads the reusable archetype metadata (canonical project, default data/
feature/model/trading/robustness config) from configs/archetypes/*.yaml,
and — as archetypes get implemented — hands back the concrete data
adapter / feature builder / strategy objects for the orchestrator.

Domain adapters are swappable per archetype; the validation, trading,
diagnostics and reporting stack underneath is shared (section 9).
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import pandas as pd
import yaml
from pydantic import BaseModel, Field

from project_factory.schemas import (
    Archetype,
    DataSpec,
    ModelLadder,
    TradingSpec,
)

CONFIG_DIR = Path(__file__).resolve().parent.parent / "configs" / "archetypes"


class ArchetypeConfig(BaseModel):
    archetype: Archetype
    name: str
    best_for: list[str] = Field(default_factory=list)
    canonical_title: str
    canonical_research_question: str
    economic_hypothesis: str
    statistical_hypothesis: str
    data: DataSpec
    features: list[str] = Field(default_factory=list)
    models: ModelLadder
    trading: TradingSpec = Field(default_factory=TradingSpec)
    robustness: list[str] = Field(default_factory=list)
    project_covers: list[str] = Field(default_factory=list)
    project_does_not_cover: list[str] = Field(default_factory=list)
    separate_interview_prep: list[str] = Field(default_factory=list)


class ArchetypeNotImplementedError(NotImplementedError):
    """Raised when an archetype's spec is registered but its data
    adapter / feature builder / strategy code hasn't been built yet."""


_CONFIG_CACHE: dict[Archetype, ArchetypeConfig] = {}


def _load_config(archetype: Archetype) -> ArchetypeConfig:
    path = CONFIG_DIR / f"{archetype.value}.yaml"
    if not path.exists():
        raise FileNotFoundError(
            f"No archetype config for {archetype.value!r} at {path}. "
            f"Every Archetype enum member must have a matching YAML file."
        )
    raw = yaml.safe_load(path.read_text())
    return ArchetypeConfig.model_validate(raw)


def get_archetype_config(archetype: Archetype) -> ArchetypeConfig:
    if archetype not in _CONFIG_CACHE:
        _CONFIG_CACHE[archetype] = _load_config(archetype)
    return _CONFIG_CACHE[archetype]


def all_archetype_configs() -> dict[Archetype, ArchetypeConfig]:
    return {a: get_archetype_config(a) for a in Archetype}


# --------------------------------------------------------------------------
# Implementation status: which archetypes have runnable code behind them.
# Updated as milestones land (see IMPLEMENTATION_STATUS.md).
# --------------------------------------------------------------------------

IMPLEMENTED_ARCHETYPES: set[Archetype] = set()
"""Archetypes with a working DataAdapter/FeatureBuilder/Strategy triplet
registered via register_data_adapter etc. Empty until Milestone 3 lands."""

_DATA_ADAPTERS: dict[Archetype, type] = {}
_FEATURE_BUILDERS: dict[Archetype, type] = {}
_STRATEGIES: dict[Archetype, type] = {}
_TARGET_BUILDERS: dict[Archetype, Callable[[pd.DataFrame], pd.Series]] = {}


_SYNTHETIC_DATA_ADAPTERS: dict[Archetype, type] = {}


def register_data_adapter(archetype: Archetype, adapter_cls: type) -> None:
    _DATA_ADAPTERS[archetype] = adapter_cls
    IMPLEMENTED_ARCHETYPES.add(archetype)


def register_synthetic_data_adapter(archetype: Archetype, adapter_cls: type) -> None:
    """A non-real, same-schema stand-in adapter (see data/adapters/
    synthetic_*.py) — lets `qpf run --synthetic` exercise the full
    pipeline without live data access. Never used unless explicitly
    requested."""
    _SYNTHETIC_DATA_ADAPTERS[archetype] = adapter_cls


def register_feature_builder(archetype: Archetype, builder_cls: type) -> None:
    _FEATURE_BUILDERS[archetype] = builder_cls


def register_strategy(archetype: Archetype, strategy_cls: type) -> None:
    _STRATEGIES[archetype] = strategy_cls


def register_target_builder(archetype: Archetype, target_builder) -> None:
    """target_builder: Callable[[pd.DataFrame], pd.Series] — builds the
    (forward-looking) label column from a feature frame. Archetype-
    specific because what counts as the target (a spread, a direction, a
    return) differs per project."""
    _TARGET_BUILDERS[archetype] = target_builder


def get_data_adapter(archetype: Archetype, synthetic: bool = False):
    table = _SYNTHETIC_DATA_ADAPTERS if synthetic else _DATA_ADAPTERS
    if archetype not in table:
        kind = "synthetic data adapter" if synthetic else "data adapter"
        raise ArchetypeNotImplementedError(f"{archetype.value} has no {kind} registered yet.")
    return table[archetype]()


def get_feature_builder(archetype: Archetype):
    if archetype not in _FEATURE_BUILDERS:
        raise ArchetypeNotImplementedError(
            f"{archetype.value} has no feature builder registered yet."
        )
    return _FEATURE_BUILDERS[archetype]()


def get_strategy(archetype: Archetype):
    if archetype not in _STRATEGIES:
        raise ArchetypeNotImplementedError(
            f"{archetype.value} has no strategy registered yet."
        )
    return _STRATEGIES[archetype]()


def get_target_builder(archetype: Archetype) -> Callable[[pd.DataFrame], pd.Series]:
    if archetype not in _TARGET_BUILDERS:
        raise ArchetypeNotImplementedError(
            f"{archetype.value} has no target builder registered yet."
        )
    return _TARGET_BUILDERS[archetype]
