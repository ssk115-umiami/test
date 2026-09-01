"""Minimal on-disk fetch cache (section 11.1's DataAdapter.fetch).

Deliberately dumb: hash the request key, check for a cached parquet
file, otherwise call the provided fetch function and cache the result.
No expiry policy — research data for a fixed historical window doesn't
change, so a cache hit is always valid; delete the file to force a
re-fetch.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Callable

import pandas as pd


def _cache_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()[:24]


def cached_fetch(
    cache_dir: Path,
    key: str,
    fetch_fn: Callable[[], pd.DataFrame],
) -> Path:
    """Return the path to a cached parquet file for `key`, calling
    fetch_fn() and writing it if the cache is empty."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{_cache_key(key)}.parquet"
    if not path.exists():
        df = fetch_fn()
        df.to_parquet(path)
    return path


def load_cached(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path)
