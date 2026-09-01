"""Importing this package registers every archetype with a real (or
real-but-network-untested, see individual module docstrings)
implementation, populating registry.IMPLEMENTED_ARCHETYPES. cli.py
imports this once at startup so `qpf run`/`qpf report` see accurate
coverage without every caller needing to know which archetypes exist.

Add a new archetype's `register()` call here as it's implemented.
"""

from __future__ import annotations

from project_factory.archetypes import predictive_market_making

predictive_market_making.register()
