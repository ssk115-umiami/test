# 48-Hour Quant / Trading Project Factory — Master LLM Handoff and Implementation Spec

**Version:** 1.0  
**Date:** 2026-09-01  
**Purpose:** Drop this file into a fresh LLM conversation. The receiving LLM should be able to reconstruct the exact project-selection and build engine described here, then immediately begin implementing the reusable codebase.

---

# 0. READ THIS FIRST — WHAT YOU ARE BUILDING

You are not building one research project.

You are building a **48-hour job-description-to-project factory** for quantitative trading, quantitative research, systematic hedge funds, commodity trading, energy trading, market making, and adjacent risk-taking roles.

The core workflow is:

> **Job description + insider/trader call notes + candidate context → infer what the desk actually rewards → select the highest-signal project archetype → generate a tightly scoped research specification → build/reuse the code pipeline → run statistically valid experiments → convert research into a trading/risk decision → attack the result for failure modes → package it into GitHub/resume/interview material.**

The user wants to be able to hand the system a new job description and, within approximately 48 hours, have a **genuinely defensible, impressive, interview-ready project** tailored to that role.

The system must optimize for **signal in recruiting**, not for academic novelty, code volume, or flashy machine learning.

The finished project is not considered done merely because code runs. It is done when the candidate can survive aggressive questioning on:

- why the hypothesis should exist,
- why the data is appropriate,
- what information was truly available at decision time,
- why the statistical method is valid,
- why the model fails,
- how the output becomes a position or trading decision,
- what assumptions make the backtest fragile,
- and what would invalidate the result.

This is the central philosophy of the entire engine.

---

# 1. CANDIDATE / RECRUITING CONTEXT

Assume the candidate is approximately:

- a master's student in Mathematical Finance,
- from a non-target university,
- targeting serious Northeast U.S. trading / quant / commodity / hedge-fund organizations,
- interested in quantitative trading, quantitative research, systematic trading, energy, commodities, market making, hedge funds, power, gas, metals, and eventually meaningful P&L / risk responsibility,
- willing to use analyst / research / commercial / desk-adjacent routes when they are genuinely close to market decisions,
- trying to replace a weaker school-brand signal with stronger evidence of mathematical ability, research judgment, market understanding, code fluency, and highly targeted projects.

Important candidate strategy:

> Do not optimize for prestige. Optimize for the probability that a real desk sees evidence that this candidate can think, research, model, debug, and eventually contribute to P&L.

The user wants research infrastructure automated so human time is spent on:

- applications,
- networking,
- technical preparation,
- project mastery,
- and interviews.

---

# 2. THE CRITICAL INSIGHT FROM REAL TRADER CALLS

Two trader conversations materially shaped this engine.

## 2.1 Commodity / CCI-style signal

A recent graduate trader / cross-commodities contact described a hiring and desk environment emphasizing:

- apply broadly,
- market-focused case studies,
- statistics and dataframe questions,
- some quant-style questions,
- computer architecture / understanding systems rather than merely syntax,
- **more emphasis on math than rote programming**, 
- energy commodities as a major opportunity set,
- understanding the data-generating process and frequency before deciding what statistics/modeling is appropriate,
- understanding why regularization, linear algebra, ridge regression, etc. work,
- being able to answer whether a model is statistically sound,
- theoretical ML questions in interviews,
- experienced traders increasingly needing quantitative tools as markets become more complex,
- physical causal intuition still matters, but simple one-step causal rules are increasingly insufficient.

A key anecdote: the trader's future boss asked an interview question tied to an actual research bottleneck. The candidate's theoretical answer was later used by that boss to overcome part of the problem. The candidate did not know at interview time that it was a live desk issue.

**Interpretation for the engine:**

The valuable candidate is not merely “good at coding.” The valuable candidate can:

> **understand the market mechanism → formalize it statistically → use AI/code as leverage → understand the math → identify where the model breaks → determine whether the failure is structural, statistical, or data-related.**

LLMs may write much of the code. The human must own the intellectual explanation.

## 2.2 Headlands / systematic electronic trading signal

A trader discussing a Headlands-style environment described:

- research-led firms trading largely delta-one products such as futures/stocks/bonds,
- fully systematic trading where software makes every trade,
- market data used in neural-network / time-series research,
- coding increasingly automated internally, but interviews remaining code-heavy,
- LeetCode-style coding preparation,
- standard quantitative math resources,
- data-science interviews where a candidate is handed a dataset and asked how to clean, split, model, validate, and reason about it,
- linear-algebra proof questions at the level of serious undergraduate linear algebra (e.g. Axler-style reasoning),
- researchers checking PnL, diagnosing production failures, running historical simulation experiments, and modifying strategy/data/research pipelines,
- good research ideas often emerging from understanding an existing codebase and production system,
- a strong student project being a live or simulated trading system on an accessible market,
- historical market data + market-making model as a useful project direction,
- projects generally being probed in interviews rather than forensically audited line by line,
- widespread AI use for code and alpha research,
- one trader's belief that research-generation work will increasingly be automated by agents.

Some of those industry predictions are opinions, not universal facts. The engine should not blindly accept claims such as “researchers no longer code” or “latency is unimportant.” Official job requirements still matter.

**Interpretation for the engine:**

For systematic-electronic roles, a project should show:

> **noisy market data → predictive signal → automated decision rule → simulated execution → PnL → production-style diagnostics → robustness / failure analysis.**

---

# 3. NON-NEGOTIABLE DESIGN PRINCIPLES

The next LLM must preserve these principles exactly.

## 3.1 Job description first

Do not begin with a pet project and force it onto every role.

The engine must ingest the actual job description and extract:

- asset class / market,
- systematic vs discretionary,
- trading vs research vs execution focus,
- data frequency,
- statistics / ML expectations,
- linear algebra / probability expectations,
- coding language expectations,
- software / production expectations,
- market-microstructure expectations,
- physical / fundamental market expectations,
- optimization / portfolio expectations,
- whether the role explicitly converts research to PnL.

## 3.2 Insider call notes are a second evidence layer

The official JD is the hard anchor.

Trader / employee calls add information about:

- actual interview style,
- actual day-to-day work,
- internal research culture,
- hidden bottlenecks,
- what the firm rewards in practice,
- what a strong project should demonstrate.

Do not let anecdotal opinions override explicit official requirements without flagging the discrepancy.

## 3.3 A project must be interview-generative

The best project is one that causes the interviewer to ask questions the candidate wants to answer.

A project should intentionally create openings for questions about:

- probability,
- statistics,
- linear algebra,
- model assumptions,
- regularization,
- data leakage,
- time-series validation,
- market mechanics,
- execution,
- PnL,
- debugging,
- software architecture,
- regime change,
- and model failure.

## 3.4 Simple models before complex models

Always start with a baseline.

Typical progression:

1. naive / economic baseline,
2. OLS / logistic regression,
3. regularized linear model,
4. one strong nonlinear benchmark,
5. neural / deep model only when the role and data justify it.

Do not use a neural network merely for resume optics.

## 3.5 Prediction is not enough

For trading roles, the chain must reach:

> **data → forecast / signal → uncertainty → decision → position / quotes → execution assumptions → PnL → risk → failure analysis.**

A forecasting-only project is weaker than a trading research project.

## 3.6 Failure analysis is a first-class deliverable

Most student projects stop at model comparison.

This engine must explicitly investigate:

- largest residuals,
- largest drawdowns,
- parameter instability,
- regime-specific failures,
- sensitivity to transaction costs,
- sensitivity to latency/fills where relevant,
- feature disappearance / ablation,
- training-window choice,
- data drift,
- leakage,
- and plausible economic/market causes.

A model failure that is deeply understood can be more impressive than a small improvement in headline Sharpe.

## 3.7 Ex-ante vs ex-post must be explicit

Every feature must have an `available_at` concept.

The system must distinguish:

- **ex-ante features**: legitimately available when the decision would have been made,
- **ex-post diagnostic variables**: useful for explaining a failure after the fact but illegal as predictive inputs.

This distinction is mandatory for every time-series / trading project.

## 3.8 AI writes code; the candidate owns the reasoning

The user explicitly wants heavy LLM coding assistance.

The codebase should make that safe by producing a **model-defense / interview-mastery pack** that explains:

- every major equation,
- why each model is used,
- assumptions,
- typical failure modes,
- data-timing logic,
- software architecture,
- and likely interviewer attacks.

The rule is:

> Nothing stays in the project unless the candidate can explain what it does and why it is legitimate.

---

# 4. INPUT CONTRACT

Every project run should accept the following inputs.

## 4.1 Required

- `firm_name`
- `role_title`
- `job_description`

## 4.2 Strongly preferred

- `insider_call_notes`
- `location`
- `known_interview_details`
- `application_deadline`

## 4.3 Candidate context

Store candidate context globally rather than re-entering it for every run:

```yaml
candidate:
  degree: "MS Mathematical Finance"
  school_tier: "non-target"
  target_roles:
    - quantitative_trading
    - quantitative_research
    - commodity_trading
    - systematic_research
    - hedge_fund_research
  languages:
    - python
    - cpp
  target_geography:
    - New York City
    - Greenwich CT
    - Stamford CT
    - Westchester
  strengths_to_signal:
    - mathematics
    - probability
    - statistics
    - model_reasoning
    - market_intuition
    - research_judgment
  project_time_budget_hours: 48
```

---

# 5. OUTPUT CONTRACT

Every run should create a self-contained project folder with at least:

```text
projects/<firm>_<role>_<project_slug>/
├── project_spec.yaml
├── README.md
├── RESEARCH_MEMO.md
├── INTERVIEW_MASTERY.md
├── RESUME_BULLETS.md
├── ASSUMPTIONS_AND_RISKS.md
├── DATA_DICTIONARY.md
├── requirements.txt or pyproject.toml
├── config/
├── data/
│   ├── raw/
│   ├── interim/
│   └── processed/
├── src/
├── notebooks/
├── tests/
├── reports/
│   ├── figures/
│   └── tables/
└── run_project.py
```

The project pack must include:

1. exact research question,
2. why the project matches the JD,
3. hypothesis,
4. data sources,
5. target variable,
6. information timing,
7. baseline,
8. model set,
9. validation scheme,
10. trading / decision layer,
11. robustness tests,
12. failure analysis,
13. figures/tables,
14. results summary,
15. assumptions/limitations,
16. 30-second interview explanation,
17. 2-minute explanation,
18. 10-minute technical walkthrough,
19. likely interviewer attacks + correct responses,
20. 1–2 resume bullets.

---

# 6. PROJECT ARCHETYPE REGISTRY

Do not invent a brand-new discipline for every job. Maintain a reusable registry of approximately 5–7 archetypes.

## Archetype A — Power Regime / DA–RT Research

**Best for:** commodity quant, power desks, CCI/Mercuria-style roles, energy hedge funds, power fundamental/quant roles.

Canonical project:

> **Regime-Aware Forecasting and Trading of NYISO Day-Ahead vs Real-Time Power Spreads**

Core question:

> Can an ex-ante statistical model forecast hourly DA–RT power-price dislocations, and can identifying when the model is likely to fail improve trading decisions and risk-taking?

Core ingredients:

- NYISO NYC + one comparison zone,
- DA / RT prices,
- load forecasts,
- weather forecasts,
- lagged market data,
- gas/fuel information where timing is valid,
- selected grid-state information,
- OLS,
- Ridge,
- one nonlinear benchmark,
- chronological walk-forward validation,
- residual / regime analysis,
- congestion / outage / scarcity post-mortems,
- forecast uncertainty → no-trade / sizing rule,
- PnL and drawdown analysis.

The centerpiece is not raw forecast accuracy. It is:

> **understanding where apparently stable statistical relationships fail when the physical grid regime changes.**

Do not start with FTR auction valuation. FTR/congestion is a later extension because the market mechanics can consume the entire 48-hour window.

## Archetype B — Predictive Market Making / Microstructure

**Best for:** Headlands, Jump-like research roles, Flow, Virtu, GTS, Old Mission, HFT/electronic market makers, systematic delta-one research.

Canonical project:

> **Can short-horizon order-book imbalance predict adverse price movement well enough to improve the PnL of an inventory-constrained market-making strategy after fees, latency, and fill uncertainty?**

Core pipeline:

```text
L2/trade data
→ microstructure features
→ short-horizon alpha model
→ quote adjustment / reservation price
→ execution simulator
→ PnL / inventory / adverse selection
→ stress tests
→ failure analysis
```

Typical features:

- best bid/ask imbalance,
- multi-level depth imbalance,
- microprice,
- spread,
- signed trade flow,
- recent returns,
- realized volatility,
- add/cancel intensity,
- trade intensity,
- depth / liquidity.

Model ladder:

1. symmetric/no-alpha market maker,
2. logistic or linear short-horizon model,
3. regularized linear/logistic model,
4. tree model,
5. small neural network only if justified by the JD / call.

Trading layer example:

\[
r_t = m_t + \alpha \hat{\mu}_t - \gamma q_t
\]

where:

- \(m_t\) = midprice,
- \(\hat{\mu}_t\) = expected short-horizon move,
- \(q_t\) = inventory,
- \(\alpha\) = alpha sensitivity,
- \(\gamma\) = inventory penalty.

Critical question:

> Does better predictive accuracy actually produce better trading PnL after fills, adverse selection, inventory, fees, and stale information?

Required stress tests:

- fees,
- latency / stale data assumptions,
- multiple fill models,
- adverse-selection measurement,
- inventory limits,
- volatility regimes,
- liquidity/spread regimes,
- model drift,
- walk-forward retraining.

For a 48-hour project, use an accessible liquid market with reliable historical L2/trade data. Crypto may be used as an engineering/research substrate when equities/futures L2 data is inaccessible, but the README must state clearly that the research problem is transferable electronic market microstructure, not that the instrument matches the employer's production market.

## Archetype C — Systematic Futures / Alpha Research

**Best for:** systematic macro, futures quant, CTA, hedge funds, multi-asset QR.

Canonical questions:

- Can term structure / carry / momentum / inventory / macro features predict risk-adjusted futures returns?
- Does a signal survive walk-forward testing, realistic costs, regime shifts, and parameter perturbations?

Core elements:

- multiple liquid futures or ETFs if futures data is limited,
- economically motivated factors,
- cross-sectional and/or time-series signal,
- regularized models,
- temporal CV,
- turnover / costs,
- portfolio construction,
- signal decay,
- robustness across instruments.

## Archetype D — Options / Volatility Market Making

**Best for:** options traders, vol desks, market makers.

Canonical project:

- build implied-volatility surface,
- estimate Greeks,
- simulate inventory-aware quoting,
- evaluate PnL/risk under changing volatility and spread assumptions,
- analyze model risk / hedging errors.

Potential methods:

- Black-Scholes baseline,
- local/surface interpolation,
- stochastic-volatility benchmark only if time allows,
- inventory-aware reservation prices,
- delta hedging simulation,
- vol-surface stability.

## Archetype E — Natural Gas Fundamentals / Basis

**Best for:** gas trading, energy majors, commodity funds, merchant desks.

Canonical project families:

- storage/weather/basis regime modeling,
- pipeline capacity and regional basis,
- gas-to-power coupling,
- demand/weather forecast errors and price response.

The project must retain physical-market interpretation rather than becoming generic futures ML.

## Archetype F — Cross-Sectional / Stat-Arb Research

**Best for:** equity quant hedge funds, systematic equity research, stat arb.

Core elements:

- universe construction,
- feature normalization,
- cross-sectional prediction,
- neutralization,
- temporal validation,
- turnover/costs,
- portfolio constraints,
- decay,
- crowding/regime robustness.

## Archetype G — Physical Commodity Economics

**Best for:** metals merchants, oil/refined-products desks, physical commodity trading organizations.

Examples:

- LME vs COMEX economics,
- inventory/warehouse/physical premium relationships,
- refinery/blending economics,
- crude/product differentials,
- freight/FX/financing/carry,
- treatment and refining charges.

This archetype may be less ML-heavy and more market-structure/commercial. It should still include a quantitative decision framework where possible.

---

# 7. ARCHETYPE ROUTING LOGIC

Implement a deterministic + LLM-assisted router.

The router should score every archetype against extracted JD/call signals.

Suggested signal dimensions:

```yaml
signals:
  electronic_market_microstructure: 0-5
  physical_commodity_knowledge: 0-5
  power_grid_specificity: 0-5
  natural_gas_specificity: 0-5
  options_volatility: 0-5
  cross_sectional_equities: 0-5
  systematic_delta_one: 0-5
  time_series_ml: 0-5
  neural_network_emphasis: 0-5
  statistics_emphasis: 0-5
  linear_algebra_emphasis: 0-5
  coding_interview_emphasis: 0-5
  production_software_emphasis: 0-5
  execution_emphasis: 0-5
  pnl_ownership: 0-5
  fundamental_market_reasoning: 0-5
  low_frequency_commercial: 0-5
```

Example routing rules:

- If `electronic_market_microstructure >= 4` AND `systematic_delta_one >= 4` → Archetype B.
- If `power_grid_specificity >= 4` OR (`physical_commodity_knowledge >= 3` AND `power` mentioned repeatedly) → Archetype A.
- If `natural_gas_specificity >= 4` → Archetype E.
- If `options_volatility >= 4` → Archetype D.
- If `cross_sectional_equities >= 4` → Archetype F.
- If `systematic_delta_one >= 3` AND no dominant microstructure/power/options signal → Archetype C.
- If `low_frequency_commercial >= 3` AND metals/oil/physical language dominates → Archetype G.

The router must return:

- `primary_archetype`
- `secondary_archetype`
- `routing_confidence`
- `why_primary_matches`
- `what_primary_does_not_cover`
- `interview_prep_needed_to_cover_gap`

Do not choose a hybrid project merely to satisfy every possible signal. A focused project plus targeted interview prep is usually better than an incoherent mega-project.

---

# 8. PROJECT SPEC SCHEMA

Every chosen project should be represented as structured YAML/JSON before code generation.

Example:

```yaml
project:
  project_id: "headlands_predictive_market_making_v1"
  firm: "Headlands Technologies"
  role: "Quantitative Researcher"
  archetype: "predictive_market_making"
  title: "Predictive Market Making from Limit-Order-Book Data"

research_question: >
  Can short-horizon order-book imbalance predict adverse price movement
  well enough to improve the PnL of an inventory-constrained market-making
  strategy after fees, latency, and fill uncertainty?

hypothesis:
  economic: >
    Temporary supply/demand imbalance visible in the order book and recent
    order flow contains short-horizon information about mid-price changes
    and adverse-selection risk.
  statistical: >
    Regularized and nonlinear models may extract signal from correlated,
    noisy microstructure features, but gains in predictive accuracy may not
    translate monotonically into trading PnL.

data:
  market_type: "electronic_limit_order_book"
  instrument: null
  frequency: "event_or_subsecond"
  sources: []
  required_fields:
    - timestamp
    - bid_price_levels
    - ask_price_levels
    - bid_size_levels
    - ask_size_levels
    - trades
  timestamp_policy: "strictly_ex_ante"

features:
  - top_level_imbalance
  - multi_level_imbalance
  - microprice
  - spread
  - signed_trade_flow
  - short_horizon_returns
  - realized_volatility
  - trade_intensity

models:
  baseline:
    - no_alpha_symmetric_market_maker
  predictive:
    - logistic_regression
    - ridge_or_regularized_logistic
    - gradient_boosted_tree
    - small_neural_network

validation:
  scheme: "walk_forward"
  random_kfold_allowed: false
  leakage_audit: true

trading:
  alpha_to_quotes: true
  inventory_penalty: true
  fees: true
  fill_uncertainty: true
  latency_stress_test: true
  adverse_selection_measurement: true

robustness:
  - fee_sensitivity
  - latency_sensitivity
  - fill_model_sensitivity
  - volatility_regimes
  - spread_regimes
  - feature_ablation
  - training_window_sensitivity
  - model_drift

outputs:
  figures_target: 6
  tables_target: 4
  resume_bullets: 2
  interview_questions_target: 30
```

---

# 9. REUSABLE CODEBASE ARCHITECTURE

Build one reusable repository called something like:

```text
quant_project_factory/
```

Recommended structure:

```text
quant_project_factory/
├── README.md
├── pyproject.toml
├── .gitignore
├── configs/
│   ├── candidate.yaml
│   └── archetypes/
│       ├── power_da_rt.yaml
│       ├── predictive_market_making.yaml
│       ├── systematic_futures.yaml
│       ├── options_market_making.yaml
│       ├── gas_basis.yaml
│       ├── stat_arb.yaml
│       └── physical_commodity.yaml
├── project_factory/
│   ├── __init__.py
│   ├── cli.py
│   ├── schemas.py
│   ├── jd_parser.py
│   ├── router.py
│   ├── spec_builder.py
│   ├── orchestrator.py
│   ├── registry.py
│   ├── data/
│   │   ├── base.py
│   │   ├── cache.py
│   │   ├── timestamps.py
│   │   ├── quality.py
│   │   └── adapters/
│   ├── features/
│   │   ├── base.py
│   │   ├── time_series.py
│   │   ├── microstructure.py
│   │   ├── power.py
│   │   └── futures.py
│   ├── models/
│   │   ├── base.py
│   │   ├── linear.py
│   │   ├── tree.py
│   │   ├── neural.py
│   │   └── diagnostics.py
│   ├── validation/
│   │   ├── walk_forward.py
│   │   ├── leakage.py
│   │   ├── bootstrap.py
│   │   └── robustness.py
│   ├── trading/
│   │   ├── signals.py
│   │   ├── sizing.py
│   │   ├── costs.py
│   │   ├── pnl.py
│   │   ├── inventory.py
│   │   └── execution/
│   ├── diagnostics/
│   │   ├── residuals.py
│   │   ├── regime.py
│   │   ├── stability.py
│   │   ├── feature_ablation.py
│   │   └── failure_cases.py
│   ├── reporting/
│   │   ├── plots.py
│   │   ├── tables.py
│   │   ├── memo.py
│   │   ├── readme.py
│   │   ├── resume.py
│   │   └── interview.py
│   └── templates/
├── projects/
└── tests/
```

The important engineering choice is that **domain adapters are replaceable but validation/trading/reporting components are reusable.**

---

# 10. RECOMMENDED TECH STACK

Use a boring, maintainable stack.

Core:

- Python 3.11+
- pandas
- numpy
- scipy
- scikit-learn
- statsmodels
- pyarrow
- pydantic
- PyYAML
- typer (CLI)
- requests or httpx
- matplotlib
- pytest

Optional by archetype:

- xgboost or lightgbm
- PyTorch for small neural baselines
- duckdb for larger local data
- polars only if data scale warrants it

Do not over-engineer infrastructure before the first end-to-end project runs.

---

# 11. CORE SOFTWARE INTERFACES

Implement explicit interfaces so the LLM can churn projects quickly.

## 11.1 Data adapter

```python
class DataAdapter(Protocol):
    def fetch(self, spec: ProjectSpec) -> Path: ...
    def load(self, spec: ProjectSpec) -> pd.DataFrame: ...
    def validate(self, df: pd.DataFrame, spec: ProjectSpec) -> DataQualityReport: ...
```

## 11.2 Feature builder

```python
class FeatureBuilder(Protocol):
    def transform(self, df: pd.DataFrame, spec: ProjectSpec) -> pd.DataFrame: ...
    def feature_manifest(self) -> list[FeatureDefinition]: ...
```

Each `FeatureDefinition` should include:

- name,
- description,
- economic rationale,
- source columns,
- calculation,
- `available_at` logic,
- ex_ante boolean,
- leakage risk notes.

## 11.3 Model wrapper

```python
class ResearchModel(Protocol):
    def fit(self, X, y): ...
    def predict(self, X): ...
    def diagnostics(self, X, y): ...
```

## 11.4 Validation engine

```python
class WalkForwardValidator:
    def split(...): ...
    def run(...): ...
```

Must preserve chronological order.

## 11.5 Strategy / decision engine

```python
class Strategy(Protocol):
    def decisions(self, predictions, market_state, spec): ...
    def evaluate(self, decisions, realized, spec): ...
```

## 11.6 Failure analyzer

```python
class FailureAnalyzer:
    def largest_errors(...): ...
    def largest_drawdowns(...): ...
    def regime_breakdown(...): ...
    def parameter_stability(...): ...
    def ablations(...): ...
```

## 11.7 Reporter

The reporter should generate Markdown and figures automatically from experiment metadata rather than relying on manually written final summaries.

---

# 12. EXPERIMENT TRACKING

Every run should produce a machine-readable experiment record.

Example:

```json
{
  "experiment_id": "ridge_alpha_10_window_60d",
  "project_id": "nyiso_da_rt_v1",
  "train_start": "2024-01-01",
  "train_end": "2024-06-30",
  "test_start": "2024-07-01",
  "test_end": "2024-07-31",
  "features": ["load_forecast", "temperature", "lagged_spread"],
  "model": "ridge",
  "params": {"alpha": 10},
  "predictive_metrics": {},
  "trading_metrics": {},
  "diagnostic_metrics": {},
  "notes": []
}
```

Store experiments as JSON/JSONL/Parquet initially. Do not build a database server unless needed.

---

# 13. THE 48-HOUR OPERATING CYCLE

The system should deliberately timebox scope.

## Hours 0–2 — JD / call analysis

- parse JD,
- parse insider notes,
- score archetypes,
- select primary project,
- identify missing role signals that must be covered through interview prep rather than the project,
- generate `project_spec.yaml`.

## Hours 2–8 — data and baseline

- identify 1–3 reliable data sources,
- download/cache data,
- validate timestamps,
- build target,
- build minimal features,
- produce naive baseline,
- sanity-check distributions.

If usable data cannot be acquired quickly, switch to the closest project-compatible dataset. Do not lose 20 hours fighting a perfect dataset.

## Hours 8–18 — core models

- fit baseline,
- fit interpretable statistical model,
- fit regularized model,
- fit at most one strong nonlinear benchmark,
- run chronological validation.

## Hours 18–28 — trading layer + failure analysis

- convert output into trading/decision rule,
- incorporate costs/constraints relevant to the archetype,
- analyze largest errors/drawdowns,
- test regimes,
- test leakage,
- test parameter/feature sensitivity.

This block is more important than adding a fifth model.

## Hours 28–36 — research iteration

Use results to change one or two meaningful aspects of the research.

Examples:

- remove a leaky feature,
- change training window,
- add a regime variable,
- change target horizon,
- adjust no-trade threshold,
- modify inventory penalty,
- simplify a model that is unstable.

## Hours 36–44 — packaging

Generate:

- final 5–8 figures,
- final tables,
- README,
- research memo,
- assumptions/limitations,
- clean repo structure.

## Hours 44–48 — candidate mastery

Generate and drill:

- 30-second explanation,
- 2-minute explanation,
- 10-minute deep dive,
- mathematical derivations,
- dataset/timestamp questions,
- market questions,
- debugging questions,
- 25–40 likely interviewer attacks,
- resume bullet(s).

A project is not finished until this stage is complete.

---

# 14. QUALITY GATES — THE SYSTEM SHOULD REFUSE TO CALL A PROJECT DONE IF THESE FAIL

## Gate 1 — Causal / economic rationale

Can the candidate explain why the relationship might exist?

If no, project is not done.

## Gate 2 — Information timing

Is every predictive feature demonstrably available when the decision is supposedly made?

If unclear, mark the feature as unsafe and exclude it from the primary backtest.

## Gate 3 — Baseline

Is there a simple benchmark that the complex model must beat?

If no, project is not done.

## Gate 4 — Correct validation

For time-series research, random train/test splitting is prohibited unless a very specific argument justifies it.

## Gate 5 — Trading translation

For a trading role, does the signal become a decision/position/quote and then PnL/risk?

If no, project is incomplete.

## Gate 6 — Fragility testing

Have costs, regimes, parameter choices, and feature dependence been stressed?

## Gate 7 — Failure cases

Have the largest mistakes / drawdowns been investigated?

## Gate 8 — Candidate defense

Can the candidate explain the model from first principles at the level implied by the JD?

## Gate 9 — No fake claims

Never claim:

- live profitability when only backtested,
- executable fills when using naive touch assumptions,
- causality from correlation,
- production-grade latency realism without evidence,
- market data availability that was not verified.

---

# 15. HOW TO USE MATHEMATICS AS A RECRUITING SIGNAL

The project should deliberately expose mathematical questions.

For regularization, candidate should be able to discuss:

\[
\hat\beta_{ridge}=(X^TX+\lambda I)^{-1}X^Ty
\]

and answer:

- What objective is being minimized?
- Why does \(L_2\) regularization shrink coefficients?
- What happens as \(\lambda\to0\)?
- What happens as \(\lambda\to\infty\)?
- Why does feature scaling matter?
- Why can ridge help with collinearity / poor conditioning?
- How do eigenvalues / singular values enter the explanation?
- Why doesn't ridge generally create exact zeros?
- What bias does it introduce?
- Why might it still fail out of sample?

For time series:

- stationarity,
- autocorrelation,
- residual behavior,
- distribution shift,
- walk-forward testing,
- multiple testing,
- look-ahead bias,
- regime dependence.

For Headlands-style roles, add serious linear algebra/proof preparation outside the project as well.

---

# 16. HOW TO USE CODING AS A RECRUITING SIGNAL

Do not optimize for memorizing syntax.

The project code should show:

- clean module boundaries,
- reproducibility,
- basic tests,
- caching,
- deterministic experiment configs,
- explicit timestamp handling,
- readable diagnostics,
- ability to scale conceptually.

Candidate should know enough systems concepts to discuss:

- stack vs heap,
- memory hierarchy,
- cache locality,
- contiguous arrays,
- process vs thread,
- latency,
- vectorization,
- why NumPy behaves differently from Python loops,
- basic complexity,
- I/O and network bottlenecks.

For code-heavy firms, project creation does **not** replace LeetCode / interview coding prep.

---

# 17. HEADLANDS EXEMPLAR — EXACT ROUTING RESULT

## Input signal from JD

Headlands Quantitative Researcher role emphasizes:

- portfolio of automated electronic trading strategies,
- predictive signals and trading models,
- measurable strategy PnL improvement,
- ownership from hypothesis through production,
- systematic trading interest,
- statistics + ML on noisy real-world data,
- Java/C++/Python,
- profitable, scalable, maintainable strategies.

## Input signal from trader call

- fully systematic delta-one research,
- software makes every trade,
- market data / neural networks / time series,
- coding-heavy interview despite increased AI coding internally,
- dataset-cleaning/modeling interview questions,
- linear algebra proof questions,
- production debugging and PnL monitoring,
- historical simulations / experiments,
- market-making project recommended,
- AI used heavily in research.

## Routing result

**Primary archetype:** Predictive Market Making / Microstructure  
**Secondary:** Systematic Futures / Alpha Research

## Canonical Headlands project

**Title:** Predictive Market Making from Limit-Order-Book Data

**Research question:**

> Can short-horizon order-book imbalance predict adverse price movement well enough to improve the PnL of an inventory-constrained market-making strategy after fees, latency, and fill uncertainty?

## Why this is superior to the power project for Headlands

The power project still demonstrates statistical reasoning, but this project directly maps to:

- electronic market data,
- predictive signals,
- automated trading,
- PnL,
- market making,
- noisy data,
- production/debugging mindset.

The power project remains the better primary project for energy / commodity desks.

---

# 18. ENERGY / CCI EXEMPLAR — EXACT ROUTING RESULT

## Input signal

- commodity trading / energy,
- market-focused case studies,
- stats and dataframe questions,
- math and linear algebra / regularization understanding,
- increasing quantification of historically intuitive physical relationships,
- need to understand physical mechanism and model failure,
- project should use market data at an appropriate frequency.

## Routing result

**Primary archetype:** Power Regime / DA–RT Research

## Canonical project

**Title:** When the Grid Breaks the Model: Regime-Aware Forecasting of NYISO Day-Ahead / Real-Time Power Spreads

**Research question:**

> How predictable is the hourly DA–RT power-price spread under normal conditions, how does predictability break down as the physical state of the grid changes, and can model uncertainty improve trading decisions?

Model ladder:

- baseline,
- OLS,
- Ridge,
- one nonlinear model.

The project should investigate:

- multicollinearity,
- conditioning,
- rolling coefficients,
- residuals,
- congestion regimes,
- outage/scarcity periods,
- strict ex-ante timing,
- no-trade / sizing based on uncertainty.

---

# 19. REPORTING / RECRUITING OUTPUTS

Every project should produce versions of the research for different audiences.

## 19.1 Resume bullet

One or two lines, technical but readable.

Example Headlands-style:

> Developed a systematic market-making research pipeline using historical level-2 order-book data; modeled short-horizon price movement from order-flow and liquidity features using regularized linear, tree-based, and neural models; integrated forecasts into inventory-aware quoting and evaluated PnL under walk-forward validation, latency, fees, fill uncertainty, adverse selection, and changing market regimes.

Example energy-style:

> Built a regime-aware statistical model of NYISO day-ahead/real-time power spreads using ex-ante load, weather and grid-state data; compared OLS, Ridge and nonlinear forecasts under walk-forward validation, diagnosed model failures across congestion regimes, and translated forecast uncertainty into risk-adjusted trading decisions.

## 19.2 30-second explanation

Should answer:

- what did I study,
- why did it matter,
- what did I find / learn?

## 19.3 2-minute explanation

Add:

- target,
- data,
- model ladder,
- validation,
- trading layer,
- biggest failure insight.

## 19.4 10-minute explanation

Add:

- equations,
- architecture,
- feature timing,
- robustness,
- alternative explanations,
- what would change in production.

## 19.5 Interview attack sheet

Generate questions across:

- statistics,
- probability,
- linear algebra,
- ML,
- data cleaning,
- leakage,
- market mechanics,
- execution,
- PnL/risk,
- systems,
- debugging,
- project limitations.

---

# 20. DO NOT OVERFIT THE PROJECT TO THE FIRM NAME

The project should be role-aligned without pretending to replicate proprietary strategies.

Never claim:

- “this is how Headlands trades,”
- “this is how CCI prices power,”
- “this is how a Millennium pod trades.”

Use language such as:

> “This project is designed to demonstrate the research and decision-making skills emphasized by the role: noisy-data modeling, systematic validation, PnL translation, and failure analysis.”

---

# 21. DATA-SOURCE SELECTION RULES

The next LLM should use current web research when selecting data sources.

Prefer:

1. official exchange / ISO / regulator / government data,
2. documented APIs,
3. reputable public datasets,
4. vendor/free-tier datasets when reproducible.

Before committing to a project, verify:

- data is downloadable,
- data covers enough history,
- timestamps are understandable,
- licensing allows project use,
- target and critical features are actually available,
- acquisition does not consume the entire 48-hour budget.

If an ideal dataset is inaccessible, switch to a close substitute and document the limitation.

---

# 22. PROJECT SCOPE DISCIPLINE

The 48-hour factory wins by refusing scope creep.

Default maximum for a first version:

- 1 primary instrument / market + 1 comparison market at most,
- 3–4 main model families,
- 1 trading layer,
- 5–8 final figures,
- 3–5 core robustness analyses,
- 1 strong failure-analysis section.

Examples of bad scope:

- all NYISO + PJM + ERCOT + FTR auctions in one weekend,
- 10 ML models,
- a production exchange connector plus research plus dashboard plus live deployment,
- an entire options stack + vol surface + RL market maker in 48 hours.

Depth and defensibility beat breadth.

---

# 23. AUTOMATIC PROJECT-SELECTION PROMPT CONTRACT

The codebase may use an LLM for qualitative routing/spec generation. The prompt should be approximately:

> You are the research director of a quantitative trading project factory. Given a job description, insider call notes, and candidate context, infer what the role actually rewards. Select the single best project archetype from the registry. Do not choose a hybrid merely to cover every keyword. The project must be finishable to a credible first version in 48 hours with public/accessible data. Optimize for interview signal: statistics, mathematics, data handling, market reasoning, PnL translation, robustness, and failure analysis. Return structured JSON matching ProjectSpec. Explicitly state which role requirements the project covers, which it does not cover, and what separate interview preparation is required.

Do not let the model output arbitrary prose only. Validate against a Pydantic schema.

---

# 24. FIRST IMPLEMENTATION MILESTONE

The receiving LLM should **start coding immediately** after reading this file.

Do not begin by writing another strategy essay.

## Milestone 1 — skeleton + routing engine

Create:

1. `pyproject.toml`
2. `project_factory/schemas.py`
3. `project_factory/registry.py`
4. `project_factory/jd_parser.py`
5. `project_factory/router.py`
6. `project_factory/spec_builder.py`
7. `project_factory/cli.py`
8. archetype YAML templates
9. tests for parsing/routing

### CLI target

```bash
qpf analyze-role \
  --jd examples/headlands_jd.txt \
  --call examples/headlands_call.txt \
  --out projects/headlands/
```

Expected outputs:

```text
projects/headlands/
├── ROLE_ANALYSIS.md
├── project_spec.yaml
└── routing.json
```

Then:

```bash
qpf init-project --spec projects/headlands/project_spec.yaml
```

creates the project repository from templates.

## Milestone 2 — reusable research core

Implement:

- timestamp-safe feature manifest,
- walk-forward validation,
- baseline/linear/regularized model wrappers,
- experiment recording,
- standard predictive metrics,
- standard trading metrics,
- standard diagnostics.

## Milestone 3 — Archetype B first end-to-end

Implement the Headlands microstructure project first because it exercises:

- data adapter,
- high-frequency-ish feature engineering,
- prediction,
- strategy conversion,
- execution assumptions,
- PnL,
- failure analysis.

## Milestone 4 — Archetype A second

Implement NYISO power project using the same reusable validation/diagnostic/reporting stack.

If these two work, the architecture is sufficiently general to support the remaining archetypes.

---

# 25. PSEUDOCODE FOR THE ORCHESTRATOR

```python
def build_project(input_bundle: RoleInput) -> ProjectRun:
    role_analysis = parse_role(input_bundle)

    routing = route_archetype(role_analysis)

    spec = build_project_spec(
        role_analysis=role_analysis,
        routing=routing,
        candidate=load_candidate_config(),
    )

    project_dir = initialize_project(spec)

    adapter = registry.get_data_adapter(spec.archetype)
    feature_builder = registry.get_feature_builder(spec.archetype)
    strategy = registry.get_strategy(spec.archetype)

    raw = adapter.fetch(spec)
    df = adapter.load(spec)
    data_report = adapter.validate(df, spec)

    features = feature_builder.transform(df, spec)
    run_leakage_audit(features, spec)

    experiments = []
    for model_spec in spec.models:
        result = run_walk_forward_experiment(
            features=features,
            model_spec=model_spec,
            validation_spec=spec.validation,
        )
        experiments.append(result)

    strategy_results = strategy.evaluate_models(experiments, features, spec)

    failures = FailureAnalyzer(spec).analyze(
        experiments=experiments,
        strategy_results=strategy_results,
        data=features,
    )

    robustness = run_robustness_suite(spec, experiments, strategy_results)

    reports = Reporter(spec).build_all(
        role_analysis=role_analysis,
        experiments=experiments,
        strategy_results=strategy_results,
        failures=failures,
        robustness=robustness,
    )

    return ProjectRun(...)
```

---

# 26. MINIMUM TEST SUITE

Before trusting outputs, write tests for:

- chronological split ordering,
- no overlap between train/test windows,
- feature `available_at` compliance,
- PnL sign conventions,
- inventory limits,
- transaction-cost deduction,
- deterministic configs/seeds,
- missing-data handling,
- target alignment,
- no accidental future joins,
- execution simulator edge cases.

For microstructure, explicitly test that future book/trade states cannot enter current features.

For energy, explicitly test that forecast/publication timestamps are aligned to when the trader could know them.

---

# 27. WHAT THE ENGINE MUST NOT BECOME

Do not let this become:

- a generic Kaggle wrapper,
- an “LLM generates 20 indicators” toy,
- a backtest curve factory,
- a resume-bullet generator disconnected from real research,
- an excuse to avoid math/interview prep,
- a fake production trading system,
- a months-long software platform that delays applications.

The architecture exists only to produce **high-signal, defensible research artifacts quickly**.

---

# 28. HOW PROJECTS AND INTERVIEW PREP SPLIT THE WORK

No single project perfectly targets every firm.

Example:

A NYISO project is excellent for energy/commodity organizations and still useful for quant research, but it does not replace HFT microstructure preparation.

A market-making project is excellent for Headlands/Flow/Virtu/Old Mission-style roles, but it does not prove physical power-market knowledge.

Therefore each role analysis must output:

```yaml
project_covers:
  - ...
project_does_not_cover:
  - ...
separate_interview_prep:
  - probability
  - mental_math
  - leetcode
  - linear_algebra_proofs
  - systems_architecture
  - market_specific_knowledge
```

This prevents project scope from exploding.

---

# 29. RECRUITING RESEARCH CONTEXT THAT INFORMED THIS ENGINE

The broader recruiting work concluded that the candidate should target a mixture of:

- CCI / Castleton Commodities,
- Mercuria,
- STX,
- Gerald Group,
- Concord Resources,
- Ocean Partners,
- Karbone,
- Traxys,
- InCommodities,
- Danske Commodities,
- Statkraft,
- Flow Traders,
- Headlands,
- Old Mission,
- DV Trading,
- GTS,
- Squarepoint,
- Tower,
- Virtu,
- plus energy majors / trading organizations such as Shell/BP/EDF/RWE-type firms when roles are genuinely tied to trading/fundamentals/commercial decisions.

The implication is that the project factory must support both:

1. **physical/fundamental commodity + quantitative hybrid roles**, and
2. **pure systematic/electronic quantitative research/trading roles**.

This is why the engine uses archetype routing rather than one universal project.

---

# 30. HOW TO REASON ABOUT PROJECT IMPRESSIVENESS

A project is **not** impressive because:

- it uses a neural network,
- it has thousands of lines of code,
- it has a pretty dashboard,
- it reports a high Sharpe,
- it uses an exotic model.

A project becomes impressive when the interviewer realizes the candidate:

- formed a coherent hypothesis,
- understood the market/data-generating process,
- used appropriate statistics,
- caught leakage or bad assumptions,
- compared simple and complex models intelligently,
- converted the model into a real decision framework,
- investigated failures,
- understood what would break in production,
- can explain the math,
- can explain the software,
- and can say what they would do next.

This is the single most important qualitative standard.

---

# 31. BOOT INSTRUCTIONS FOR THE NEXT LLM

When this file is pasted into a new LLM conversation, the next model should behave as follows:

1. **Acknowledge that the goal is to implement the reusable 48-hour project factory, not merely discuss it.**
2. **Do not ask the user to re-explain the strategy contained in this file.**
3. If a job description and call notes are already provided, parse them immediately.
4. Create the codebase skeleton first.
5. Implement the schemas/router/spec generator.
6. Use the Headlands example as the first integration fixture.
7. Produce a valid `project_spec.yaml` for Headlands.
8. Then implement the reusable research core.
9. Then begin the Headlands microstructure project end-to-end.
10. Keep every component reusable for the NYISO project next.
11. Do not add infrastructure that is not needed for one of the first two projects.
12. Maintain a running `IMPLEMENTATION_STATUS.md` with:
    - completed,
    - currently building,
    - blockers,
    - next command to run.
13. If external data/API details are needed, research current official sources rather than guessing.
14. If a data source blocks progress for more than a reasonable fraction of the 48-hour budget, switch to a substitute and document the tradeoff.
15. Generate interview-mastery documentation alongside code, not as an afterthought.

---

# 32. FIRST USER-FACING COMMANDS THE FINISHED FACTORY SHOULD SUPPORT

Ideal CLI:

```bash
# 1. Analyze a role and choose a project
qpf analyze-role \
  --jd headlands_jd.txt \
  --call headlands_call.txt

# 2. Inspect generated spec
qpf show-spec projects/headlands/project_spec.yaml

# 3. Initialize project files
qpf init-project --spec projects/headlands/project_spec.yaml

# 4. Acquire / validate data
qpf run --spec projects/headlands/project_spec.yaml --stage data

# 5. Run research
qpf run --spec projects/headlands/project_spec.yaml --stage models

# 6. Run strategy and robustness
qpf run --spec projects/headlands/project_spec.yaml --stage trading
qpf run --spec projects/headlands/project_spec.yaml --stage robustness

# 7. Generate recruiting pack
qpf report --spec projects/headlands/project_spec.yaml

# Or run/resume everything
qpf run --spec projects/headlands/project_spec.yaml --all --resume
```

The `--resume` behavior matters. Project runs should cache completed stages so a failed data/model/report step does not destroy prior work.

---

# 33. FINAL OPERATING FORMULA

For every new job description:

> **Read the JD → read the insider notes → infer the actual research/trading loop → choose one archetype → define a falsifiable hypothesis → verify accessible data → build a baseline → use interpretable math → add one stronger model → validate chronologically → translate to PnL/risk → attack the result → package it → drill the candidate.**

And the candidate-facing principle is:

> **Use the LLM to move faster. Never outsource understanding.**

That is the engine.

---

# 34. IMMEDIATE NEXT ACTION

The receiving LLM should now **start writing the repository**, beginning with:

- `pyproject.toml`
- `project_factory/schemas.py`
- `project_factory/registry.py`
- `project_factory/jd_parser.py`
- `project_factory/router.py`
- `project_factory/spec_builder.py`
- `project_factory/cli.py`
- `configs/archetypes/predictive_market_making.yaml`
- `configs/archetypes/power_da_rt.yaml`
- `tests/test_router.py`
- `examples/headlands_jd.txt`
- `examples/headlands_call.txt`

The first test is successful when the CLI reads the Headlands example and deterministically produces:

```yaml
primary_archetype: predictive_market_making
secondary_archetype: systematic_futures
```

plus a Headlands project spec matching the design in this handoff.

After that, code the reusable walk-forward / experiment / reporting core and begin the microstructure implementation.

**Do not return to brainstorming unless a genuine implementation blocker appears.**
