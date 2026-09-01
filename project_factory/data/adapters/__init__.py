"""Per-archetype DataAdapter implementations.

bybit_l2.py: BybitPublicDataAdapter — real Bybit public trades + L2
order-book archive for Archetype B. See its module docstring for exactly
what is and isn't independently network-verified (this sandbox blocks
the relevant domains).
synthetic_microstructure.py: SyntheticMicrostructureAdapter — same
column schema, used for tests and pipeline development; not real data
(see its module docstring).

Milestone 4 adds a NYISO/weather adapter for Archetype A here.
"""
