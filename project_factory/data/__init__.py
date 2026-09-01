"""Data layer (section 11.1).

- base.py: DataAdapter protocol.
- cache.py: dumb on-disk fetch cache (parquet, keyed by request string).
- timestamps.py: assert_ex_ante / LookaheadError — the actual mechanism
  behind "strictly_ex_ante" in DataSpec.timestamp_policy.
- quality.py: DataQualityReport (duplicates, gaps, missingness, sort order).

Per-archetype adapters live in data/adapters/ (Milestone 3/4).
"""
