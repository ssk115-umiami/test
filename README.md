# quant_project_factory

A 48-hour job-description-to-project factory for quantitative trading /
quantitative research / commodity / energy / market-making roles.

Given a job description (+ optional insider call notes), the factory:

1. parses the JD/notes into scored signals across 17 dimensions,
2. routes to one of 7 reusable project archetypes,
3. generates a structured `project_spec.yaml`,
4. scaffolds a self-contained project folder (README, research memo,
   interview-mastery pack, resume bullets, data dictionary, code layout),
5. runs the actual research: walk-forward validated models, a trading/
   decision layer, robustness stress tests, and failure analysis —
   working end-to-end for `predictive_market_making` as of Milestone 3.

Full design rationale lives in the original handoff spec; this repo is the
implementation. See `IMPLEMENTATION_STATUS.md` for exactly what's built.

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Usage

```bash
# 1. Analyze a role and choose a project archetype
qpf analyze-role \
  --jd examples/headlands_jd.txt \
  --call examples/headlands_call.txt \
  --out projects/headlands/

# 2. Inspect the generated spec
qpf show-spec projects/headlands/project_spec.yaml

# 3. Scaffold the project folder
qpf init-project --spec projects/headlands/project_spec.yaml

# 4+. Run research / trading / robustness stages, then generate the
# recruiting pack. Only archetypes in IMPLEMENTED_ARCHETYPES have a
# working pipeline (currently: predictive_market_making) — see
# IMPLEMENTATION_STATUS.md.
qpf run --spec projects/<id>/project_spec.yaml --all --resume
qpf report --spec projects/<id>/project_spec.yaml

# Try the whole pipeline right now without any data access, using the
# synthetic (non-real, clearly-labeled) data adapter:
qpf run --spec projects/<id>/project_spec.yaml --all --synthetic
qpf report --spec projects/<id>/project_spec.yaml
```

Two fixtures are included under `examples/`: a Headlands-style systematic
electronic-trading JD (routes to `predictive_market_making`) and a
CCI-style power/energy JD (routes to `power_da_rt`) — these are the two
archetypes implemented first (Milestones 3 and 4) because together they
exercise the full reusable stack: data adapter, feature timing, walk-forward
validation, a trading/decision layer, and failure analysis. The real data
adapter for `predictive_market_making` (Bybit's public trades/order-book
archive) has not been network-verified from the sandbox this was built
in — see the verification-status note in
`project_factory/data/adapters/bybit_l2.py` and
`IMPLEMENTATION_STATUS.md` before trusting it; `qpf run --synthetic`
exercises the identical pipeline against generated data with a known
injected signal in the meantime.

## Architecture

```text
project_factory/
├── schemas.py       # Pydantic contracts: RoleInput -> RoleAnalysis -> RoutingResult -> ProjectSpec
├── jd_parser.py      # deterministic keyword/heuristic signal scoring
├── router.py          # section-7 rules -> primary/secondary archetype
├── spec_builder.py    # RoleAnalysis + RoutingResult -> ProjectSpec
├── registry.py         # archetype config loader + data/feature/strategy/target registry
├── init_project.py      # scaffolds projects/<id>/ from a ProjectSpec
├── orchestrator.py        # run_stage(): data -> models -> trading -> robustness
├── experiments.py           # ExperimentRecord + walk-forward experiment runner
├── cli.py                     # `qpf` commands
├── archetypes/                 # per-archetype wiring (registers adapter/features/strategy/target)
├── data/, features/, models/, validation/, trading/, diagnostics/, reporting/
│   # reusable research core, see IMPLEMENTATION_STATUS.md for exact coverage
configs/
├── candidate.yaml         # global candidate context (section 4.3)
└── archetypes/*.yaml      # per-archetype canonical project + defaults
projects/                  # generated project folders (git-ignored data/)
```

The design choice that makes this reusable: **domain adapters are
swappable per archetype (data source, features, strategy); the
validation, diagnostics, and reporting stack underneath is shared.**

## Quality gates

A generated project is not "done" just because code runs. See section 14
of the handoff spec (causal rationale, information timing / ex-ante
discipline, a real baseline, correct chronological validation, a trading
translation, fragility testing, failure-case analysis, candidate defense,
no fake claims) — these gates are enforced by the reusable core as it
lands (walk-forward-only validation, `available_at` feature timing audit,
mandatory baseline comparison, etc.).
