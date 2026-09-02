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
- ~~Order-book parsing only reads `snapshot` records, dropping `delta`
  records between snapshots~~ — fixed in Round 3 (see below); full
  snapshot+delta reconstruction is now implemented and sampled at a
  configurable interval.
- The robustness sweep automates 2 of ~8 items in section 6's list
  (fee/latency sensitivity); the rest are implemented as callable
  `FailureAnalyzer`/model methods but not wired into an automated sweep.
- No small-neural-network step (ladder step 5) — per section 3.4, not
  added without a role-specific justification.

## Cross-cutting infrastructure added alongside Milestone 4

Requested explicitly (not archetype-specific) — built once, used by both
Bybit and NYISO adapters:

- `data/errors.py` — a shared exception taxonomy every real adapter uses
  instead of letting a raw httpx/parsing exception escape:
  `DataSourceNetworkError` (couldn't reach the host at all),
  `DataSourceHTTPError` (reached it, non-2xx response),
  `DataSourceSchemaError` (response received, structure didn't match
  what's expected), `DataSourceQualityError` (parsed fine, failed a
  quality check). This is what makes network vs. schema vs. quality
  failures distinguishable at a glance instead of reading a stack trace
  (requested deliverable #4 below).
- `data/cache.py` — new `fetch_bytes_with_local_fallback(raw_dir,
  filename, fetch_fn)`. `filename` is the source's OWN native filename
  (Bybit's `BTCUSDT_2024-06-01.csv.gz`, NYISO's
  `20240601damlbmp_zone.csv`) rather than a hash, so a file you download
  yourself (browser, curl, the source's own bulk tools) and drop into
  the adapter's raw directory with its original name is picked up
  automatically — `path.exists()` short-circuits before any network
  call. Both `BybitPublicDataAdapter` and `NyisoPowerDataAdapter` use
  this exclusively; no separate "fixture mode" to keep in sync.
- `data/verification.py` — `mark_verified`/`verification_status`,
  persisted as `.verified.json` in each adapter's cache dir. A real
  adapter's `load()` calls `mark_verified` ONLY after it actually
  succeeds against real downloaded/local data (both Bybit and NYISO
  adapters do this); `validate()` reports `verified` in the
  `DataQualityReport`. Never true for synthetic data, never true for a
  real adapter just because its code looks well-documented.
- `data/quality.py` — `DataQualityReport` gained `source_kind`
  (`"real"`/`"synthetic"`/`"unknown"`) and `verified: bool`, both set by
  every adapter's `validate()`.
- `orchestrator.py` — the `data` stage now persists
  `reports/data_quality.json` (previously only `trading`/`robustness`
  results were persisted).
- `reporting/memo.py` + `qpf report` — read `data_quality.json` and
  prepend a loud banner ("SYNTHETIC DATA — NOT REAL RESULTS" or
  "UNVERIFIED DATA SOURCE") to every generated results section AND print
  it to the terminal, whenever `source_kind == "synthetic"` or
  `verified == False`. This is the enforcement mechanism behind "synthetic
  data must never be presented as research evidence" — not just a
  docstring promise.
- `trading/pnl.py` — refactored into a shared `_standard_result()` plus
  two thin assemblers: `assemble_trading_result` (mark-to-market,
  continuously-held inventory — market making) and
  `assemble_periodic_trading_result` (periodic settlement, a fresh
  position each period against that period's realized outcome — power).
  Both produce the identical dict shape, which is what lets
  `reporting/memo.py` stay archetype-agnostic. See "architecture changes"
  below for why they're not the same function.

**Milestone 4 — Archetype A end-to-end (NYISO power DA/RT)**

### Data-source verification note (same sandbox constraint as Milestone 3)

`data/adapters/nyiso.py` is unusually well cross-confirmed for something
that couldn't be hit directly in this sandbox: a web search independently
reported the URL pattern, AND `gridstatus`
(github.com/kmax12/gridstatus — a maintained open-source library other
people run against live NYISO data) was fetched directly via
`raw.githubusercontent.com` (reachable here) and its `nyiso.py` source
read line by line, independently confirming dataset names, exact URL
construction, the daily-vs-monthly-zip retention split, and raw CSV
column names. Full detail, including what's still NOT confirmed (exact
zone-name string formatting, whether the ~7-day retention window is
current), is in the module's own docstring. Per Gate 9, still not
treated as verified — `verification_status(...).verified` is `False`
until a real `load()` succeeds in an unrestricted environment.

### Completed

- `data/adapters/synthetic_power.py` — `SyntheticPowerDataAdapter`:
  hourly DA/RT LBMP + load forecast with a genuine injected regime
  signal (contiguous "scarcity" blocks where an unexplained shock
  dominates the spread) — directly encodes the archetype's own research
  question (does predictability break down in certain regimes?) rather
  than being uniformly learnable everywhere. Same output schema as the
  real adapter.
- `data/adapters/nyiso.py` — `NyisoPowerDataAdapter`: real adapter for
  NYISO's public MIS CSV archive (day-ahead LBMP, real-time LBMP, load
  forecast), with the daily-CSV/monthly-zip fallback `gridstatus` uses,
  local-file ingestion, `check_connectivity()`, and the shared error
  taxonomy. Parsing functions (`_parse_lbmp_csv`,
  `_parse_load_forecast_csv`) are unit-tested against fixtures in the
  documented format directly.
- `features/power.py` — `PowerFeatureBuilder` (calendar features, lagged
  spread, rolling spread mean/std, DA price, load forecast — all
  `available_at`-audited) + `build_target` (same-row `da_rt_spread`,
  legitimate because it's realized strictly after `decision_time`, no
  shift needed — contrast with the market-making archetype's
  forward-shifted label).
- `trading/no_trade_sizing.py` — `NoTradeSizingStrategy`: a no-trade band
  plus capped, scaled position sizing (section 6's "uncertainty ->
  no-trade / sizing rule"), reusing `trading/costs.py` and the new
  `assemble_periodic_trading_result`.
- `project_factory/archetypes/power_da_rt.py` — registers the real
  adapter, synthetic adapter, feature builder, strategy, target builder,
  and (new) `task_type="regression"` with the registry.
- Tests: `test_synthetic_power.py`, `test_power_features.py`,
  `test_no_trade_sizing.py`, `test_nyiso_adapter_parsing.py`,
  `test_orchestrator_power.py`, plus the new
  `test_local_ingestion.py` covering both adapters — **106/106 tests
  passing overall** (73 from Milestones 1-3 + 33 new), ruff clean.
  Verified: the leakage audit passes on the power feature builder's own
  output; scarcity-regime rows have >2x the average spread magnitude of
  normal rows (the injected regime signal is real); higher fees never
  improve PnL for the sizing strategy either; a network-free test proves
  both real adapters use manually-dropped local files with **zero**
  network calls (`monkeypatch` raises `AssertionError` if `httpx.get`/
  `httpx.head` is ever called) and correctly call `mark_verified`;
  `test_orchestrator_power.py::test_same_orchestrator_code_serves_both_archetypes_without_branching`
  asserts `orchestrator.py`'s source contains no archetype-name
  conditionals; full `data -> models -> trading -> robustness` pipeline
  verified through the real CLI (`qpf run --all --synthetic` then `qpf
  report`) exactly as Milestone 3 was, including the verification banner
  actually appearing in the terminal and in `README.md`/`RESEARCH_MEMO.md`.

### Architecture changes Milestone 4 forced (the actual generalization findings)

Three real bugs/gaps in the "generic" orchestrator built during Milestone
3, all found by `test_orchestrator_power.py` failing before these fixes
— i.e., the Milestone 3 code LOOKED archetype-agnostic but wasn't fully:

1. **`_run_robustness_suite` hardcoded `MarketMakingStrategy(...)`
   directly** with a fixed parameter list (`alpha`, `gamma`,
   `half_spread_ticks`, ...) that doesn't exist on
   `NoTradeSizingStrategy`. Fixed by reconstructing `type(strategy)`
   with parameters introspected from the actual instance (`vars(strategy)`)
   and only sweeping `fee_bps`/`latency_ticks` when the strategy instance
   actually has that attribute — `latency_sensitivity` is correctly
   *absent* from the power archetype's robustness output rather than
   forced into an economically meaningless concept for a strategy with
   no notion of quote staleness.
2. **`task_type` defaulted to `"classification"`** in `run_stage()`'s
   signature — silently wrong for a regression archetype. Fixed by
   adding `registry.register_task_type`/`get_task_type` (same
   override-then-registry pattern as every other per-archetype
   dependency) and changing the default to `None`, resolved per-call.
3. **A hardcoded `"logistic_regression"` fallback** (used when a spec's
   model-ladder name doesn't resolve) would have crashed
   `build_model(name, task_type="regression")`. Replaced with
   `_default_model_name(task_type)`.
4. (Not a bug fix, a genuine design split, documented above) —
   `trading/pnl.py`'s equity assembly needed two mechanics
   (`assemble_trading_result` vs. `assemble_periodic_trading_result`)
   because mark-to-market inventory (continuously held, priced against a
   market) and periodic signal-based positions (a fresh bet each period
   against that period's own realized outcome, no meaningful
   between-period "price" to mark against) are genuinely different
   market structures — forcing them into one function would have meant
   either a wrong PnL calculation for one archetype or a leaky
   abstraction with archetype-conditional branches inside it. The
   *shape* of the result (the dict keys) is still fully shared, which is
   what actually matters for `reporting/memo.py`.

Everything else — the walk-forward validator, the leakage auditor, the
model factory (`ridge`/`ols`/`gradient_boosted_tree` already covered
power's model ladder with zero changes), the experiment recorder, the
data-quality/verification machinery, the CLI, the reporter's figures/
table generation — worked for `power_da_rt` completely unchanged.

## Round 1 real-data verification: Bybit fixed after a live 404

A real run against `BybitPublicDataAdapter` (outside this sandbox)
reported connectivity OK but `HTTP 404` on the order-book URL. Root-
caused by cloning and reading
`github.com/nssanta/Bybit-Download-OrderBook-Trades-Klines`'s actual
downloader source + README directly (via `raw.githubusercontent.com`
and a shallow clone, both reachable in this sandbox) rather than
re-guessing from search snippets — two real bugs, both fixed:

1. The order-book URL was missing a market-type path segment
   (`.../orderbook/spot/{SYMBOL}/...`, not `.../orderbook/{SYMBOL}/...`).
2. The adapter's default date range predated Bybit's order-book archive
   entirely — that archive only exists from **May 2025** onward (trades
   goes back to 2020, which is why that half worked). Defaults are now
   inside the confirmed window, and the constructor raises a clear
   `ValueError` for an out-of-window `start` instead of a confusing 404.

Also fixed: `check_connectivity()` previously checked only the trades
endpoint (different host than order-book) — exactly how a broken
order-book URL passed connectivity and only failed at `load()`. It now
checks both independently.

Confirmed unchanged and NOT the cause: the JSONL record schema/parsing
logic (`_parse_orderbook_records`), and the trades URLs. Full detail,
including exact depth (200 levels, kept to top 5) and frequency (~200ms
snapshots) confirmed from the same source, is in `bybit_l2.py`'s module
docstring and `VERIFICATION_GUIDE.md` §1.

New regression tests: `test_orderbook_url_includes_market_segment`,
`test_orderbook_url_futures_uses_linear_segment`,
`test_start_date_before_orderbook_availability_window_raises`,
`test_check_connectivity_checks_both_trades_and_orderbook`, plus a
schema-accurate fixture test built field-for-field from that repo's own
parser (`test_parse_orderbook_records_handles_full_confirmed_record_shape`).
113/113 tests passing, ruff clean.

## Round 2 real-data verification: Bybit trades schema mismatch

Verification progressed past the Round 1 fix and reached real trades
data — and hit `DataSourceSchemaError: could not find side/size columns
in trades data`. Actual observed columns:
`['id', 'timestamp', 'price', 'volume', 'side', 'rpi']`. Root-caused by
cloning **`github.com/bybit-exchange/docs`** — Bybit's own official API
docs source repo — and reading `docs/v5/market/recent-trade.mdx`
directly, rather than blindly renaming `size` to `volume`:

- `volume` = the archived CSV's name for the live API's `size` field,
  confirmed denominated in the **base asset** (that doc's own example:
  price=16618.49, size=0.00012 → ~$2 notional, only sensible in base
  units) — added to the accepted size-column names.
- `side` confirmed to hold exactly `Buy`/`Sell`, documented as "side of
  **taker**" (the aggressor) — confirms the existing sign convention
  (Buy=+size, Sell=-size) needed no change. Unrecognized values now
  raise `DataSourceSchemaError` naming them, rather than silently
  contributing zero.
- `rpi` (archived name for `isRPITrade`, Bybit's Retail Price
  Improvement liquidity program, Feb 2025) confirmed unrelated to
  direction/size — safely ignored, not treated as an error.
- `id` (archived name for `execId`) — an identifier, unused.
- Timestamp units were not directly confirmed for the archived CSV's
  `timestamp` column specifically (a different field name than the live
  API's `time`) — `_parse_trade_timestamps` now infers seconds vs.
  milliseconds vs. microseconds from magnitude instead of assuming, and
  raises rather than silently mis-parsing an implausible value. All
  Bybit timestamps are UTC (exchange-wide convention).

New regression tests:
`test_aggregate_trades_to_seconds_matches_real_observed_bybit_schema`
(uses the exact real observed column set),
`test_aggregate_trades_to_seconds_raises_on_unrecognized_side_value`,
`test_parse_trade_timestamps_infers_seconds_vs_milliseconds`,
`test_parse_trade_timestamps_raises_on_implausible_magnitude`.
117/117 tests passing, ruff clean.

Also documented (module docstring, "RAW FILES ARE NEVER DELETED"): every
real fetch already writes its raw bytes to `raw_trades_dir`/
`raw_orderbook_dir` with Bybit's own filenames before any parsing, and
nothing removes them — once §1 of the verification guide succeeds, those
exact files can be copied into `tests/fixtures/` for a real (not
schema-accurate-but-constructed) test fixture. See
`VERIFICATION_GUIDE.md` §1 for the exact commands.

`NyisoPowerDataAdapter` has not yet been run against live data — still
fully unverified.

## Round 3 real-data verification: Bybit order-book under-sampling (2 rows/day)

Verification progressed past Rounds 1-2 (connectivity, URL, trades
schema) and produced a syntactically valid but useless result:
`df.shape == (2, 23)` for a full trading day, with timestamps
`2025-06-01 00:00:00.948` and `2025-06-02 00:00:00.947`. Root cause: the
adapter only ever parsed `type == "snapshot"` records and silently
dropped every `delta` record; Bybit's archive apparently conveys almost
the entire book through deltas, so the previous implementation was
discarding nearly the whole day. This exact gap had been flagged as a
scope-cut in the Round 1 docstring ("delta reconstruction remains ...
not-yet-built") — it turned out to be the actual bug rather than an
optional refinement.

**Fix**: implemented full snapshot+delta order-book reconstruction
(`_LiveOrderBook`, `_apply_record`, `_reconstruct_and_sample_orderbook`
in `bybit_l2.py`), root-caused against Bybit's own documented protocol
(cloned `bybit-exchange/docs`, `v5/websocket/public/orderbook.mdx`) and
cross-checked against Bybit's officially-linked reference implementation
(pybit's `_process_delta_orderbook`, fetched at the exact commit that
repo's FAQ links to) rather than re-guessed:

- Every `snapshot` fully replaces the book; every `delta` deletes
  (`size == 0`) / inserts / updates a price level, applied in sequence.
- The reconstructed top-5 book is sampled on a fixed grid
  (`sampling_interval_ms`, new constructor argument, default 1000ms —
  `DEFAULT_SAMPLING_INTERVAL_MS`) instead of emitted on every raw update
  (documented native cadence ~100ms would be ~864,000 rows/day —
  intractable and far finer than this archetype's prediction horizon
  needs). The sampling loop applies every record with `timestamp <= grid
  point` before taking that grid point's sample, so a later message can
  never leak into an earlier sample (lookahead safety).
- `seq`/`u` are tracked as diagnostics (`n_sequence_anomalies`,
  `n_resets`, `n_deltas_before_snapshot`, `n_malformed`), not assumed to
  increment by exactly 1 (Bybit's docs don't commit to that).
- Investigated the `2025-06-02 00:00:00.947` boundary timestamp: `_dates()`
  fetches exactly one file for `start == end` (confirmed by code
  inspection, not a date-range bug) — the record is most likely a
  boundary/closing record embedded in that single file, a common
  daily-archive convention; not independently confirmable from bytes in
  this sandbox.

**`validate()` no longer marks a result verified from a clean parse
alone** — the exact gap that let the 2-row result through originally.
It now runs `_orderbook_output_sanity()` (row count vs. expected from
`sampling_interval_ms`, median cadence, crossed-book fraction,
nonpositive-size count) and only calls `mark_verified()` if all four
checks pass; the sanity result and reconstruction event counts are both
appended to `DataQualityReport.notes` either way, so a failing run
explains itself.

New regression tests (`test_bybit_adapter_parsing.py`):
`test_live_order_book_snapshot_then_delta_update_insert_delete`,
`test_live_order_book_second_snapshot_fully_resets`,
`test_reconstruct_and_sample_orderbook_applies_deltas_before_snapshot_grid_point`,
`test_reconstruct_and_sample_orderbook_does_not_look_ahead`,
`test_reconstruct_and_sample_orderbook_counts_deltas_before_snapshot_and_sequence_anomalies`,
`test_reconstruct_and_sample_orderbook_second_snapshot_counted_as_reset`,
`test_reconstruct_and_sample_orderbook_empty_input_returns_empty_frame_not_error`,
`test_orderbook_output_sanity_flags_the_round_3_two_row_failure` (reproduces
the exact real failure shape and asserts it's now rejected),
`test_orderbook_output_sanity_flags_crossed_book_and_nonpositive_size`,
`test_orderbook_output_sanity_passes_for_a_well_formed_dense_day`. Also
updated `test_local_ingestion.py`'s Bybit local-fixture test: a
single-record fixture now correctly comes back `verified=False` (sparse
data must fail the sanity gate even via the local-file path), and a new
test confirms a fixture that IS dense enough for its configured
`sampling_interval_ms` does get marked verified.
**125/125 tests passing, ruff clean.**

The one-day local verification command is unchanged in shape (see
`VERIFICATION_GUIDE.md` §1, "Round 3 finding") — only the expected output
changed, from 2 rows to roughly one row per second (~86,400 for a full
day at the default sampling interval). This still could not be confirmed
against live Bybit data from this sandbox.

## Round 4 real-data verification: Bybit is now verified; two integrity gaps fixed

A real run confirmed the Round 3 fix: **`(86401, 23)`, 1s median
cadence, 430,315 records reconstructed (2 snapshots / 430,313 deltas), 0
sequence anomalies, 0 malformed records, 0 crossed books, 0 nonpositive
top-of-book sizes.** This is the first Bybit run that actually passed
`_orderbook_output_sanity()` and got marked `verified=True` against live
data. Two follow-up data-integrity checks were requested before model
work — both turned out to be real bugs, not just unconfirmed assumptions:

1. **Half-open date window.** The `86401`st row was the Round 3
   archive-boundary record (`2025-06-02 00:00:00.947`) — Round 3 had
   explained it but not excluded it. `load()` now clips the concatenated
   order-book frame to `[start, end + 1 day)`, dropping any record dated
   on/after the day after `end`; the dropped-row count is recorded in
   `adapter._last_orderbook_diagnostics["n_rows_outside_requested_window"]`.
2. **Trade volume was silently forward-filled onto quiet seconds.**
   `_aggregate_trades_to_seconds` only emits rows for seconds that
   actually had trades (sparse); feeding that sparse frame directly into
   `merge_asof(direction="backward")` meant a quiet second's order-book
   row matched whatever earlier second last had activity, repeating its
   volume/count instead of reporting zero — real trade-flow contamination
   at every "current" quiet second in the whole dataset until the next
   real trade. Fixed with `_densify_trade_seconds()`, which reindexes the
   sparse aggregate onto a continuous one-row-per-second grid (explicit
   `0.0` for quiet seconds) before the asof match, so the match can only
   land on the current second's own bucket.
   `trade_signed_volume`/`trade_count` were already computed
   independently per second (two `.agg()` columns from one groupby) —
   that part was correct; only the merge step was wrong.

New regression tests: `test_densify_trade_seconds_fills_zero_not_forward_fill`,
`test_densify_trade_seconds_empty_input_returns_all_zero_grid`,
`test_bybit_adapter_excludes_out_of_window_boundary_record`,
`test_bybit_adapter_load_zero_fills_quiet_seconds_not_forward_fill`.
**129/129 tests passing, ruff clean.**

Full detail (including the exact real-run diagnostics and both fixture
recipes) is in `VERIFICATION_GUIDE.md` §1's "Round 4 finding".

## Blockers

- Milestones 1-4 complete and tested (129/129).
  - **Bybit is verified against real data as of Round 4** (pending one
    more confirmation run to see the exact shape become `(86400, 23)`
    after the window-clip fix — not yet re-run against live data from
    this session).
  - `NyisoPowerDataAdapter` has not been run against live data yet (not
    yet attempted).
  - **Real fixture preservation is blocked on this sandbox's lack of
    network access**: the successful Round 3/4 runs happened in the
    user's own local environment (per the Milestone 4 local-ingestion
    design), so the actual downloaded `BTCUSDT_2025-06-01.csv.gz` /
    `2025-06-01_BTCUSDT_ob200.data.zip` bytes are not present anywhere in
    this session (confirmed by searching the filesystem — nothing under
    `data_cache/` and no matching files outside this session's own
    synthetic pytest fixtures). See `VERIFICATION_GUIDE.md` §1's
    "Preserving a real fixture" section for the exact commands to copy
    them locally; they need to reach this repo (e.g. committed on this
    branch from the user's machine) before a real-fixture test can be
    added here.
- See the companion verification guide for exact commands, expected
  schemas, and how to read each adapter's failure modes.

## Next command to run

```bash
source .venv/bin/activate
pytest tests/ -v   # confirm Milestones 1-4 + all four Bybit rounds still green (129/129)
```

Then, outside this sandbox: re-run the Bybit verification sequence (§1's
command) once more to confirm the Round 4 window-clip fix (expect
`(86400, 23)`, not `86401`), then the NYISO sequence for the first time
(both in `VERIFICATION_GUIDE.md`). Once both show `verified: true`, and
once the two real raw files are committed into `tests/fixtures/bybit_raw/`
(see the Blockers note above), the natural next steps are the packaging /
interview-mastery pass (section 13, hours 36-48) and, if desired,
extending either archetype (NYISO comparison-zone spread features; a
weather data source for the power archetype).

A first real-data `predictive_market_making` research pass (baseline ->
regularized linear/logistic -> GBT, walk-forward validation, basic
quoting/PnL) was requested next. The full pipeline for this already
exists (Milestone 3's `orchestrator.run_stage` + `qpf run`/`qpf report`)
and was re-confirmed end-to-end in this session via
`qpf run --all --synthetic` + `qpf report` (mechanical regression check
only, synthetic data, discarded afterward — never presented as real
results). Running it against real data requires the real Bybit cache
this sandbox cannot produce; see the chat response for the exact command
and the ask to report back real results from the user's own environment.
