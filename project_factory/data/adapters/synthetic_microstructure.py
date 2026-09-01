"""Synthetic L2 snapshot generator for Archetype B.

This is NOT real market data and must never be presented as such (Gate
9). It exists to let the feature/model/validation/trading/diagnostics
pipeline be built and tested end-to-end inside this sandboxed session,
where outbound network access to real exchange domains is blocked (see
IMPLEMENTATION_STATUS.md). It implements the same `DataAdapter` protocol
and produces the same column schema (features/microstructure.py's
SNAPSHOT_SCHEMA) as the real BybitPublicDataAdapter, so archetype code
written/tested against this adapter needs no changes to run against real
data once that adapter is verified outside the sandbox.

The generator injects a small, known, decaying AR(1) "informed flow"
latent signal into both the order-book imbalance and the next-step price
return, on top of substantial noise — deliberately weak and noisy like
real short-horizon microstructure signal, not a toy the model trivially
solves.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from project_factory.data.cache import cached_fetch, load_cached
from project_factory.data.quality import DataQualityReport, build_quality_report

DEFAULT_CACHE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data_cache" / "synthetic_microstructure"


class SyntheticMicrostructureAdapter:
    def __init__(
        self,
        n_rows: int = 3000,
        seed: int = 0,
        signal_strength: float = 0.8,
        cache_dir: Path | None = None,
    ):
        self.n_rows = n_rows
        self.seed = seed
        self.signal_strength = signal_strength
        self.cache_dir = cache_dir or DEFAULT_CACHE_DIR

    def fetch(self, spec=None) -> Path:
        key = f"synthetic_microstructure_{self.n_rows}_{self.seed}_{self.signal_strength}"
        return cached_fetch(self.cache_dir, key, self._generate)

    def load(self, spec=None) -> pd.DataFrame:
        return load_cached(self.fetch(spec))

    def validate(self, df: pd.DataFrame, spec=None) -> DataQualityReport:
        return build_quality_report(
            df,
            timestamp_column="timestamp",
            expected_frequency=pd.Timedelta(seconds=1),
            source_kind="synthetic",
            verified=False,
        )

    def _generate(self) -> pd.DataFrame:
        rng = np.random.default_rng(self.seed)
        n = self.n_rows

        # AR(1) latent "informed order flow" signal in roughly [-1, 1].
        latent = np.zeros(n)
        for i in range(1, n):
            latent[i] = 0.85 * latent[i - 1] + rng.normal(scale=0.35)
        latent = np.clip(latent, -1.5, 1.5) / 1.5

        price = np.empty(n)
        price[0] = 100.0
        noise = rng.normal(scale=0.0015, size=n)
        for i in range(n - 1):
            step = self.signal_strength * 0.0006 * latent[i] + noise[i + 1]
            price[i + 1] = price[i] * np.exp(step)

        tick = price * 0.0002
        base_size = 50.0

        data: dict[str, np.ndarray] = {
            "timestamp": pd.date_range("2024-01-01", periods=n, freq="s"),
        }
        for level in range(1, 6):
            level_decay = 1.0 / level
            bid_noise = rng.normal(scale=5.0, size=n)
            ask_noise = rng.normal(scale=5.0, size=n)
            data[f"bid_price_{level}"] = price - level * tick
            data[f"ask_price_{level}"] = price + level * tick
            data[f"bid_size_{level}"] = np.clip(
                base_size * (1 + 0.6 * latent * level_decay) + bid_noise, 1.0, None
            )
            data[f"ask_size_{level}"] = np.clip(
                base_size * (1 - 0.6 * latent * level_decay) + ask_noise, 1.0, None
            )

        trade_noise = rng.normal(scale=8.0, size=n)
        data["trade_signed_volume"] = 10.0 * latent + trade_noise
        data["trade_count"] = rng.poisson(lam=3.0, size=n).astype(float)

        return pd.DataFrame(data)
