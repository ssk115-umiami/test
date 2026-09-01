# Implementation Status

Source of truth for what's actually built vs. what's still spec. Updated
after each milestone chunk. See `48_Hour_Quant_Project_Factory_LLM_Handoff.md`
for the full design (section numbers below refer to it).

## Completed

**Milestone 1 — skeleton + routing engine** (sections 24, 32 acceptance criteria met)

- `pyproject.toml`, package skeleton (`project_factory/` + all section-9
  subpackages stubbed with docstrings describing what each will hold).
- `project_factory/schemas.py` — full Pydantic contracts: `RoleInput`,
  `CandidateConfig`, `SignalScores` (17 dims, section 7),
  `RoleAnalysis`, `RoutingResult`, `ProjectSpec` (section 8 schema).
- `project_factory/jd_parser.py` — deterministic keyword/heuristic
  signal scorer. Word-boundary matching (not naive substring) to avoid
  false positives (e.g. bare "generation" no longer fires on
  "research-generation"). Flags anecdotal/opinion claims in call notes
  separately from hard JD requirements (section 3.2).
- `project_factory/router.py` — implements the exact ordered rules from
  section 7, plus a continuous weighted score per archetype (used for
  secondary-archetype selection and routing_confidence).
- `project_factory/spec_builder.py` — RoleAnalysis + RoutingResult +
  CandidateConfig -> ProjectSpec, using the archetype's canonical config
  as the template.
- `project_factory/registry.py` — loads `configs/archetypes/*.yaml` into
  `ArchetypeConfig`; holds the (currently empty) data-adapter /
  feature-builder / strategy registry the orchestrator will use.
- All 7 archetype YAML configs written (`power_da_rt`,
  `predictive_market_making`, `systematic_futures`,
  `options_market_making`, `gas_basis`, `stat_arb`,
  `physical_commodity`) with canonical title/research question,
  hypotheses, data/feature/model/trading defaults, robustness suite, and
  project_covers/does_not_cover/separate_interview_prep.
- `project_factory/init_project.py` — scaffolds the full section-5
  project folder layout (README, RESEARCH_MEMO, INTERVIEW_MASTERY,
  RESUME_BULLETS, ASSUMPTIONS_AND_RISKS, DATA_DICTIONARY,
  requirements.txt, run_project.py, config/data/src/notebooks/tests/reports
  dirs) with spec-derived (not empty) starter content.
- `project_factory/cli.py` (`qpf`) — `analyze-role`, `show-spec`,
  `init-project` fully working; `run` / `report` wired to defer into
  `orchestrator` / `reporting.memo` once an archetype is registered as
  implemented (currently none — see below), with a clear error otherwise.
- Fixtures: `examples/headlands_jd.txt` + `headlands_call.txt`
  (systematic electronic trading), `examples/cci_jd.txt` +
  `cci_call.txt` (power/energy commodity desk).
- Tests: `tests/test_jd_parser.py`, `tests/test_router.py`,
  `tests/test_spec_builder.py`, `tests/test_init_project.py` — **12/12
  passing**, including the section-24 acceptance test (Headlands fixture
  deterministically routes to `primary=predictive_market_making,
  secondary=systematic_futures`) and the section-18 CCI exemplar
  (`primary=power_da_rt`).
- Verified end-to-end manually:
  `qpf analyze-role --jd examples/headlands_jd.txt --call
  examples/headlands_call.txt --out projects/headlands/` then
  `qpf init-project --spec projects/headlands/project_spec.yaml`
  produces the exact folder layout from section 5.

## Currently building / not yet started

**Milestone 2 — reusable research core** (not started)

- `project_factory/data/base.py` (`DataAdapter` protocol, section 11.1),
  `cache.py`, `timestamps.py`, `quality.py`.
- `project_factory/features/base.py` (`FeatureBuilder` protocol +
  `FeatureDefinition` with `available_at`/`ex_ante`, section 11.2).
- `project_factory/models/base.py` (`ResearchModel` protocol, section
  11.3) + `linear.py` (OLS/Ridge/Logistic wrappers), `tree.py` (GBT),
  `diagnostics.py`. `neural.py` deferred until an archetype needs it.
- `project_factory/validation/walk_forward.py` (chronological-only
  `WalkForwardValidator`, section 11.4) + `leakage.py` (audits every
  feature's `available_at` against decision time).
- Experiment recording (section 12) — JSON/JSONL records, no DB.
- `project_factory/orchestrator.py` (pseudocode in section 25) —
  `run_stage()` is what `qpf run --stage ...` currently imports and will
  call once this lands.

**Milestone 3 — Archetype B end-to-end (predictive market making)** (not started)

- L2/trade data adapter for a liquid, accessible market (candidate:
  crypto L2 via a free/documented API, with the README stating clearly
  this is an electronic-microstructure research substrate, not a claim
  about matching any employer's actual production market — section 6,
  Archetype B).
- Microstructure feature builder (imbalance, microprice, spread, signed
  flow, realized vol, trade intensity).
- `trading/signals.py`, `sizing.py`, `costs.py`, `pnl.py`, `inventory.py`,
  `execution/` fill simulator; robustness suite (fees, latency, fill
  model, regime, ablation, drift — section 6 Archetype B list).
- `diagnostics/` FailureAnalyzer wired to real experiment output.
- `reporting/` — auto-generated figures/tables/memo from experiment
  metadata (section 11.7), replacing the placeholder text
  `init_project.py` currently seeds.
- Once this lands: `registry.register_data_adapter(Archetype.PREDICTIVE_MARKET_MAKING, ...)`
  etc. so `IMPLEMENTED_ARCHETYPES` includes it and `qpf run`/`qpf report`
  work for real.

**Milestone 4 — Archetype A end-to-end (NYISO power DA/RT)** (not started)

- NYISO OASIS data adapter (DA/RT LBMP, load forecasts) + weather data
  source (needs a documented, current API — verify before committing
  significant time, per section 21).
- Power feature builder (lagged spread, load forecast error, temperature
  deviation, congestion flags — all `available_at`-audited).
- Reuse the Milestone 2 validation/diagnostics/reporting stack unchanged;
  this is the test of whether the architecture actually generalizes.

## Blockers

- None currently blocking Milestone 1 (complete). Milestone 3's data
  adapter will need a real, verified, freely-accessible L2/trade data
  source chosen before feature work starts — this needs a short web-research
  pass (section 21) rather than guessing an API shape.
- Milestone 4's NYISO/weather data access likewise needs verification
  (current endpoint URLs, auth, history depth) before committing to it.

## Next command to run

```bash
source .venv/bin/activate
pytest tests/ -v   # confirm Milestone 1 still green before starting Milestone 2
```

Then start Milestone 2 with `project_factory/data/base.py` and
`project_factory/features/base.py` (the two Protocols everything else
depends on), followed by `validation/walk_forward.py`.
