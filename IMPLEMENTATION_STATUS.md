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

**Milestone 2 — reusable research core**

- `project_factory/data/base.py` (`DataAdapter` protocol, section 11.1),
  `cache.py` (dumb on-disk parquet fetch cache), `timestamps.py`
  (`assert_ex_ante` / `LookaheadError` — the real mechanism behind
  `strictly_ex_ante`), `quality.py` (`DataQualityReport`: duplicates,
  gaps, sort order, missingness).
- `project_factory/features/base.py` — `FeatureBuilder` protocol +
  `FeatureDefinition` (`available_at`/`ex_ante`/`leakage_risk_notes`,
  section 11.2 / section 3.7).
- `project_factory/models/base.py` (`ResearchModel` protocol) +
  `linear.py` (`NaiveBaselineModel`, `OLSModel`, `RidgeModel`,
  `LogisticModel` — ladder steps 1-3), `tree.py`
  (`GradientBoostedTreeModel` — ladder step 4), `diagnostics.py`
  (regression/classification metrics, `condition_number`,
  `coefficient_table`). Small neural baseline (ladder step 5)
  deliberately not built — section 3.4 says don't add one without a
  role-specific reason; add per-archetype if Milestone 3/4 needs it.
- `project_factory/validation/walk_forward.py` — row-count-based
  `WalkForwardValidator` (rolling or expanding window); train always
  strictly precedes test, splits always chronological, random k-fold is
  structurally impossible to request (Gate 4). `leakage.py` —
  `audit_leakage` checks every ex-ante `FeatureDefinition.available_at`
  against a decision-time column; `safe_feature_columns` excludes
  anything that fails (Gate 2).
- `project_factory/experiments.py` — `ExperimentRecord` (section 12
  schema) + `run_walk_forward_experiment` (fits/evaluates one model
  across every fold, one record per fold so drift/instability stays
  visible) + JSONL `save_experiments`/`load_experiments`.
- Tests: `test_data_quality.py`, `test_leakage.py`, `test_models.py`,
  `test_walk_forward.py`, `test_experiments.py` — **39/39 tests passing
  overall** (12 from Milestone 1 + 27 new), ruff clean. Verified: OLS
  recovers known synthetic coefficients, Ridge shrinks coefficients and
  converges to OLS as alpha->0, condition number is materially higher
  under synthetic collinearity, GBT beats the naive baseline, walk-forward
  splits are provably chronological/non-overlapping, the leakage audit
  actually catches a feature whose `available_at` is after decision time.
- **Not yet built** (moved here from the original Milestone 2 scope,
  because it can't be meaningfully written or tested without a real data
  adapter to wire against — see Milestone 3):
  `project_factory/orchestrator.py` (`run_stage()`, section 25
  pseudocode). `qpf run`/`qpf report` already defer-import it and are
  gated on `IMPLEMENTED_ARCHETYPES` (currently empty), so nothing is
  broken by its absence — `qpf analyze-role`/`show-spec`/`init-project`
  are unaffected.

**Milestone 3 — Archetype B end-to-end (predictive market making)**

### A sandbox network constraint that shaped this milestone — read this first

This development session runs in a sandbox whose egress policy blocks
every exchange/vendor/government domain reachable via `WebFetch` or raw
`curl` (`public.bybit.com`, `quote-saver.bycsi.com`, `www.nyiso.com`,
`www.eia.gov`, Kaggle, Tardis.dev — all return `connect_rejected` /
`403`). Only `raw.githubusercontent.com`, the session's own attached
GitHub repo via `api.github.com`, and the `WebSearch` tool are reachable.
That means real market data could not be fetched or independently
verified end-to-end from inside this session — see the verification-status
block at the top of `data/adapters/bybit_l2.py` for exactly what is and
isn't cross-confirmed. Per user decision, the response was to build
**both**: the real adapter (best-effort against documented behavior,
clearly flagged unverified) and a synthetic same-schema adapter so the
rest of the pipeline could actually be built and tested in this session.
Milestone 4 (NYISO/EIA/weather) will hit the identical constraint.

### Completed

- `data/adapters/synthetic_microstructure.py` —
  `SyntheticMicrostructureAdapter`: generates L2 snapshots + trade
  aggregates with a known, decaying AR(1) "informed flow" signal injected
  into both order-book imbalance and next-step returns (weak, noisy —
  not a toy). Same column schema as the real adapter, so code written
  against one needs no changes to run against the other. Never presented
  as real data (Gate 9) — every docstring/comment says so.
- `data/adapters/bybit_l2.py` — `BybitPublicDataAdapter`: real adapter
  for Bybit's public trades archive (`public.bybit.com`, URL pattern
  cross-confirmed by 2+ independent search results) and order-book
  archive (`quote-saver.bycsi.com`, filename convention confirmed,
  exact directory path NOT independently confirmed — see module
  docstring). `check_connectivity()` fails loudly with an actionable
  message instead of letting a parse error obscure the real problem;
  `qpf run` calls it before the data stage. The trades-CSV/orderbook-JSONL
  parsing functions (`_parse_orderbook_records`,
  `_aggregate_trades_to_seconds`) are unit-tested against the documented
  format directly (`tests/test_bybit_adapter_parsing.py`) — the live HTTP
  calls are the only untested part.
- `features/microstructure.py` — `MicrostructureFeatureBuilder`
  (top/multi-level imbalance, microprice, spread, signed trade flow,
  trade intensity, short-horizon returns, realized volatility — all
  trailing-window, all `available_at == timestamp`, so the leakage audit
  passes on the builder's own output by construction) + `build_target`
  (forward-looking binary direction label, explicitly NOT a
  `FeatureDefinition` — never a candidate model input).
- `models/factory.py` — `build_model(name, task_type, params)`: turns the
  archetype YAML's plain-string model-ladder names into the Milestone 2
  wrappers. Scoped to the names Milestones 3/4 actually use, not all 7
  archetypes' names (several, like `black_scholes_static_vol` or
  `no_alpha_symmetric_market_maker`, are pricing/strategy baselines, not
  `ResearchModel`s).
- `trading/` — `base.py` (`Strategy` protocol), `signals.py`
  (`MarketMakingStrategy`: implements section 6's
  `r_t = m_t + alpha*mu_hat_t - gamma*q_t`; `alpha=0` reproduces the
  archetype's `no_alpha_symmetric_market_maker` baseline as a quoting
  rule, not a `ResearchModel`), `costs.py` (fees), `inventory.py`
  (clipping + the `-gamma*q_t` skew), `pnl.py` (equity/PnL/Sharpe/
  drawdown/turnover), `execution/fill_simulator.py`
  (`ProbabilisticFillSimulator`: fill probability decays with distance
  from the touch; `latency_ticks` widens that distance).
- `diagnostics/failure_cases.py` — `FailureAnalyzer`: `largest_errors`,
  `largest_drawdowns`, `regime_breakdown`, `parameter_stability`,
  `feature_ablation`. One cohesive class rather than 5 tiny files (see
  its docstring for why).
- `orchestrator.py` — `run_stage()` wires
  `registry.get_data_adapter/get_feature_builder/get_strategy/get_target_builder`
  -> `audit_leakage` -> `run_walk_forward_experiment` (per model in the
  ladder) -> `Strategy.decisions/evaluate` -> a robustness sweep
  (fee_sensitivity, latency_sensitivity — the two named explicitly in
  section 6; `volatility_regimes`/`spread_regimes`/`feature_ablation`/
  `model_drift`/`fill_model_sensitivity` are available via
  `FailureAnalyzer` but not auto-run in the sweep yet, to keep runtime
  reasonable — section 22 scope discipline). Every dependency can be
  overridden (tests inject the synthetic adapter; `qpf run` uses the
  registry defaults). Trading/robustness results are persisted to
  `reports/*.json` so `qpf report` can run as a separate later step.
- `reporting/memo.py` — `build_reports()`: model-comparison table (CSV)
  + 4 figures (equity curve, inventory, fee sensitivity, latency
  sensitivity) + appends a "Results" section to `RESEARCH_MEMO.md`/
  `README.md` from the JSON/JSONL already on disk. Lean by design (see
  its docstring) rather than the fuller plots.py/tables.py/readme.py/
  resume.py/interview.py split section 9 sketches.
- `project_factory/archetypes/predictive_market_making.py` — registers
  the real adapter, the synthetic adapter (`register_synthetic_data_adapter`),
  the feature builder, the strategy, and the target builder (binary
  direction, 5-row horizon) with the registry. Importing
  `project_factory.archetypes` (done once in `cli.py`) is what makes
  `predictive_market_making` show up in `IMPLEMENTED_ARCHETYPES`.
- `qpf run --synthetic` — new flag: swaps in the synthetic adapter
  instead of the registered production one, so the full pipeline is
  demoable/testable through the actual CLI without live data access
  (prints a "do not report these results as real" warning). `qpf run`
  (no flag) calls `check_connectivity()` before the data stage and fails
  with one clean line instead of a raw traceback if the real source is
  unreachable.
- Tests: `test_synthetic_adapter.py`, `test_bybit_adapter_parsing.py`,
  `test_microstructure_features.py`, `test_trading_signals.py`,
  `test_failure_cases.py`, `test_orchestrator_market_making.py` —
  **73/73 tests passing overall** (39 from Milestones 1-2 + 34 new), ruff
  clean. Verified: the leakage audit passes on the feature builder's own
  output; higher fees never improve PnL given identical fills (proven,
  not just typically true, since fills are fee-independent by
  construction); an informed alpha signal (calibrated against the
  synthetic data's known injected signal) beats the no-alpha baseline
  across the seeds checked; `feature_ablation` correctly flags an
  informative feature over a noise feature; the full
  data->models->trading->robustness pipeline runs end-to-end through
  both direct `orchestrator.run_stage()` calls and the actual `qpf` CLI
  (`qpf run --all --synthetic` then `qpf report`, manually verified,
  producing real (non-empty, correctly-valued) figures/tables/appended
  memo sections).
- One real finding from a demo run worth noting as an example of what
  this pipeline is *for*: `condition_number` for the logistic models
  came back ~6.8e9 on the synthetic data — a legitimate, interview-ready
  multicollinearity red flag (`top_level_imbalance` and
  `multi_level_imbalance` are highly correlated by construction) that a
  candidate would need to address (e.g. drop one, or lean on the ridge
  penalty) before trusting the coefficients.

### Known gaps / honest limitations

- `BybitPublicDataAdapter`'s live HTTP calls are **not network-verified**
  in this session (see verification-status block in its docstring) — the
  next step before trusting it is running `qpf run --stage data` (no
  `--synthetic`) outside this sandbox and fixing whatever's wrong (most
  likely: the order-book archive's exact directory path).
- Order-book parsing only reads `snapshot` records, dropping `delta`
  records between snapshots (documented in `_parse_orderbook_records`) —
  a reasonable v1 scope call (section 22), full delta-based book
  reconstruction is a natural first extension once real data is flowing.
- The robustness sweep automates 2 of ~8 items in section 6's list
  (fee/latency sensitivity); the rest are implemented as callable
  `FailureAnalyzer`/model methods but not wired into an automated sweep.
- No small-neural-network step (ladder step 5) — per section 3.4, not
  added without a role-specific justification.

## Currently building / not yet started

**Milestone 4 — Archetype A end-to-end (NYISO power DA/RT)** (not started)

- NYISO OASIS data adapter (DA/RT LBMP, load forecasts) + weather data
  source (needs a documented, current API — verify before committing
  significant time, per section 21).
- Power feature builder (lagged spread, load forecast error, temperature
  deviation, congestion flags — all `available_at`-audited).
- Reuse the Milestone 2 validation/diagnostics/reporting stack unchanged;
  this is the test of whether the architecture actually generalizes.

## Blockers

- Milestones 1-3 complete and tested (73/73). The one open item from
  Milestone 3 is verifying `BybitPublicDataAdapter` against live data —
  needs an environment with normal internet access (this sandbox blocks
  it; see Milestone 3's constraint note above).
- Milestone 4's NYISO/EIA/weather data access will hit the identical
  sandbox network block — plan to research URLs/formats via `WebSearch`
  (as Milestone 3 did) and build both a real adapter (flagged unverified)
  and a synthetic one, then verify the real one outside the sandbox.

## Next command to run

```bash
source .venv/bin/activate
pytest tests/ -v   # confirm Milestones 1-3 still green (73/73) before starting Milestone 4
```

Then, outside this sandbox (normal internet access): run
`qpf run --spec <a predictive_market_making project_spec.yaml> --stage data`
(no `--synthetic`) to verify/fix `BybitPublicDataAdapter` against live
data — start with `adapter.check_connectivity()`, expect to need to
correct the order-book archive's exact directory path.

Then start Milestone 4: research-verify NYISO OASIS + a weather source
(section 21), write `data/adapters/nyiso.py` + a matching synthetic
adapter, `features/power.py`, and register them in
`project_factory/archetypes/power_da_rt.py` — reusing the Milestone 2
validation/experiments core and Milestone 3's orchestrator/reporter
unchanged is the actual test of whether this architecture generalizes.
