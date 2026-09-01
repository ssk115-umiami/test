"""Synthetic hourly DA/RT LBMP generator for Archetype A (power regime /
DA-RT research).

NOT real data — see module docstring conventions established in
data/adapters/synthetic_microstructure.py; the same rule applies here
(Gate 9, never present this as research evidence). Same output schema
as NyisoPowerDataAdapter.load() (timestamp, da_lbmp, rt_lbmp,
da_rt_spread, load_forecast, load_forecast_published_at) so code written
against one needs no changes to run against the other.

The generator explicitly encodes the archetype's central research
question: a normal regime where DA-RT spread has a small, genuinely
learnable relationship to recent history, and randomly-placed
"scarcity" blocks where an unexplained shock dominates — i.e. exactly
the kind of regime failure section 6's canonical project is about
finding and explaining, not a signal that's uniformly learnable
everywhere.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from project_factory.data.cache import cached_fetch, load_cached
from project_factory.data.quality import DataQualityReport, build_quality_report

DEFAULT_CACHE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data_cache" / "synthetic_power"


class SyntheticPowerDataAdapter:
    def __init__(
        self,
        n_hours: int = 24 * 90,
        seed: int = 0,
        scarcity_block_frac: float = 0.03,
        cache_dir: Path | None = None,
    ):
        self.n_hours = n_hours
        self.seed = seed
        self.scarcity_block_frac = scarcity_block_frac
        self.cache_dir = cache_dir or DEFAULT_CACHE_DIR

    def fetch(self, spec=None) -> Path:
        key = f"synthetic_power_{self.n_hours}_{self.seed}_{self.scarcity_block_frac}"
        return cached_fetch(self.cache_dir, key, self._generate)

    def load(self, spec=None) -> pd.DataFrame:
        return load_cached(self.fetch(spec))

    def validate(self, df: pd.DataFrame, spec=None) -> DataQualityReport:
        return build_quality_report(
            df,
            timestamp_column="timestamp",
            expected_frequency=pd.Timedelta(hours=1),
            source_kind="synthetic",
            verified=False,
        )

    def _generate(self) -> pd.DataFrame:
        rng = np.random.default_rng(self.seed)
        n = self.n_hours
        timestamps = pd.date_range("2024-01-01", periods=n, freq="h")

        hour_of_day = timestamps.hour.to_numpy()
        day_of_week = timestamps.dayofweek.to_numpy()
        diurnal = np.sin(2 * np.pi * (hour_of_day - 6) / 24.0)
        weekday_factor = np.where(day_of_week < 5, 1.0, 0.75)
        base_load = 1000.0 + 300.0 * diurnal * weekday_factor + rng.normal(scale=20.0, size=n)

        # Scarcity regime: contiguous 6-hour blocks scattered through the
        # series (more realistic than iid scarcity hours — a real grid
        # stress event lasts several hours, not one).
        is_scarcity = np.zeros(n, dtype=bool)
        n_blocks = max(1, int(n * self.scarcity_block_frac / 6))
        for _ in range(n_blocks):
            block_start = int(rng.integers(0, max(1, n - 6)))
            is_scarcity[block_start : block_start + 6] = True

        da_lbmp = 30.0 + 0.02 * base_load + rng.normal(scale=2.0, size=n)
        normal_noise = rng.normal(scale=1.5, size=n)
        scarcity_shock = np.where(is_scarcity, rng.normal(loc=40.0, scale=25.0, size=n), 0.0)
        rt_lbmp = da_lbmp + normal_noise + scarcity_shock

        load_forecast = base_load + rng.normal(scale=15.0, size=n)
        load_forecast_published_at = timestamps - pd.Timedelta(hours=20)

        return pd.DataFrame(
            {
                "timestamp": timestamps,
                "da_lbmp": da_lbmp,
                "rt_lbmp": rt_lbmp,
                "da_rt_spread": da_lbmp - rt_lbmp,
                "load_forecast": load_forecast,
                "load_forecast_published_at": load_forecast_published_at,
                # Ex-post diagnostic only (see features/power.py) — a real
                # project would use realized congestion/outage flags the
                # same way for post-mortem regime analysis, never as a
                # predictive input.
                "is_scarcity_regime": is_scarcity,
            }
        )
