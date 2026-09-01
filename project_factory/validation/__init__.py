"""Validation engine (section 11.4, Gate 2, Gate 4).

walk_forward.py: WalkForwardValidator — chronological-only splits, train
strictly precedes test, no shuffling (random k-fold is prohibited for
time series per Gate 4).
leakage.py: audit_leakage — checks every ex-ante FeatureDefinition's
available_at against a decision-time column; safe_feature_columns()
returns only what passed.

bootstrap.py / robustness.py (stress-test suite runner) land in
Milestone 3 alongside the first archetype that needs them.
"""
