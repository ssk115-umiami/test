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


def fetch_bytes_with_local_fallback(
    raw_dir: Path,
    filename: str,
    fetch_fn: Callable[[], bytes],
) -> Path:
    """Local-file/fixture ingestion path for real adapters.

    `filename` should be the data source's OWN native filename (e.g.
    Bybit's "BTCUSDT_2024-06-01.csv.gz", NYISO's
    "20240601damlbmp_zone.csv") — not a hash. That means a user who
    downloads the file directly from the source (its own bulk-download
    tool, or by hand from the exchange/ISO's website) and drops it into
    `raw_dir` with its original, unmodified name is picked up
    automatically: `path.exists()` short-circuits before `fetch_fn` (the
    network call) ever runs. No research code changes, no renaming.

    This is the single mechanism behind both "cache a network fetch" and
    "manually supply real data downloaded outside this sandbox" — they're
    the same operation from the adapter's point of view.
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / filename
    if not path.exists():
        path.write_bytes(fetch_fn())
    return path
