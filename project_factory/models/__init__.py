"""Model wrappers (section 11.3, section 3.4's model ladder).

base.py: ResearchModel protocol + ModelSpec.
linear.py: NaiveBaselineModel, OLSModel, RidgeModel, LogisticModel
(ladder steps 1-3).
tree.py: GradientBoostedTreeModel (ladder step 4 — "one strong nonlinear
benchmark").
diagnostics.py: regression/classification metrics, condition_number,
coefficient_table — the shared numbers every wrapper's diagnostics() uses.

A small neural baseline (ladder step 5) is deliberately not built yet —
section 3.4: "do not use a neural network merely for resume optics."
Add it only if a specific archetype's role signal justifies it.
"""
