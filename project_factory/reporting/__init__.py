"""Reporter (section 11.7).

memo.py's build_reports() generates figures (equity curve, inventory,
fee/latency sensitivity), a model-comparison table, and appends a
results section to RESEARCH_MEMO.md/README.md from the JSON/JSONL
experiment output already written by orchestrator.run_stage(). `qpf
report` calls this once an archetype's 'models'/'trading'/'robustness'
stages have run.
"""
