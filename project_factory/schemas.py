"""Pydantic data contracts for the quant project factory.

These are the types that flow through the pipeline described in the
handoff spec: RoleInput -> RoleAnalysis -> RoutingResult -> ProjectSpec.
Keeping them as validated schemas (rather than free-form dicts or LLM
prose) is what lets `qpf analyze-role` be deterministic and testable.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Archetype(str, Enum):
    POWER_DA_RT = "power_da_rt"
    PREDICTIVE_MARKET_MAKING = "predictive_market_making"
    SYSTEMATIC_FUTURES = "systematic_futures"
    OPTIONS_MARKET_MAKING = "options_market_making"
    GAS_BASIS = "gas_basis"
    STAT_ARB = "stat_arb"
    PHYSICAL_COMMODITY = "physical_commodity"


# --------------------------------------------------------------------------
# Section 4: input contract
# --------------------------------------------------------------------------


class RoleInput(BaseModel):
    """Everything a single `analyze-role` run needs (section 4)."""

    firm_name: str
    role_title: str
    job_description: str

    insider_call_notes: str | None = None
    location: str | None = None
    known_interview_details: str | None = None
    application_deadline: str | None = None


class CandidateConfig(BaseModel):
    """Global candidate context (section 4.3). Loaded once from
    configs/candidate.yaml rather than re-entered per run."""

    degree: str = "MS Mathematical Finance"
    school_tier: str = "non-target"
    target_roles: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    target_geography: list[str] = Field(default_factory=list)
    strengths_to_signal: list[str] = Field(default_factory=list)
    project_time_budget_hours: int = 48


# --------------------------------------------------------------------------
# Section 7: archetype routing signals
# --------------------------------------------------------------------------

SIGNAL_DIMENSIONS: list[str] = [
    "electronic_market_microstructure",
    "physical_commodity_knowledge",
    "power_grid_specificity",
    "natural_gas_specificity",
    "options_volatility",
    "cross_sectional_equities",
    "systematic_delta_one",
    "time_series_ml",
    "neural_network_emphasis",
    "statistics_emphasis",
    "linear_algebra_emphasis",
    "coding_interview_emphasis",
    "production_software_emphasis",
    "execution_emphasis",
    "pnl_ownership",
    "fundamental_market_reasoning",
    "low_frequency_commercial",
]


class SignalScores(BaseModel):
    """0-5 scores across the signal dimensions in section 7. Extra
    dimensions are rejected so the router and schema stay in lockstep."""

    electronic_market_microstructure: int = 0
    physical_commodity_knowledge: int = 0
    power_grid_specificity: int = 0
    natural_gas_specificity: int = 0
    options_volatility: int = 0
    cross_sectional_equities: int = 0
    systematic_delta_one: int = 0
    time_series_ml: int = 0
    neural_network_emphasis: int = 0
    statistics_emphasis: int = 0
    linear_algebra_emphasis: int = 0
    coding_interview_emphasis: int = 0
    production_software_emphasis: int = 0
    execution_emphasis: int = 0
    pnl_ownership: int = 0
    fundamental_market_reasoning: int = 0
    low_frequency_commercial: int = 0

    def get(self, dim: str) -> int:
        return getattr(self, dim)


class RoleAnalysis(BaseModel):
    """Structured extraction of a JD + call notes (section 3.1 / 6.1)."""

    role_input: RoleInput
    signals: SignalScores

    asset_classes: list[str] = Field(default_factory=list)
    systematic_vs_discretionary: str = "unclear"
    trading_vs_research_vs_execution: list[str] = Field(default_factory=list)
    data_frequency_hints: list[str] = Field(default_factory=list)
    languages_mentioned: list[str] = Field(default_factory=list)

    matched_keywords: dict[str, list[str]] = Field(default_factory=dict)
    """dimension -> list of keywords/phrases that fired, for auditability."""

    notes_vs_jd_discrepancies: list[str] = Field(default_factory=list)
    """Section 3.2: anecdote claims that contradict/extend the official JD."""


# --------------------------------------------------------------------------
# Section 7: router output
# --------------------------------------------------------------------------


class RoutingResult(BaseModel):
    primary_archetype: Archetype
    secondary_archetype: Archetype | None = None
    routing_confidence: float = Field(ge=0.0, le=1.0)
    why_primary_matches: list[str]
    what_primary_does_not_cover: list[str]
    interview_prep_needed_to_cover_gap: list[str]
    archetype_scores: dict[str, float] = Field(default_factory=dict)


# --------------------------------------------------------------------------
# Section 8: project spec schema
# --------------------------------------------------------------------------


class ProjectMeta(BaseModel):
    project_id: str
    firm: str
    role: str
    archetype: Archetype
    title: str


class Hypothesis(BaseModel):
    economic: str
    statistical: str


class DataSpec(BaseModel):
    market_type: str
    instrument: str | None = None
    frequency: str
    sources: list[str] = Field(default_factory=list)
    required_fields: list[str] = Field(default_factory=list)
    timestamp_policy: str = "strictly_ex_ante"


class ModelLadder(BaseModel):
    baseline: list[str] = Field(default_factory=list)
    predictive: list[str] = Field(default_factory=list)


class ValidationSpec(BaseModel):
    scheme: str = "walk_forward"
    random_kfold_allowed: bool = False
    leakage_audit: bool = True


class TradingSpec(BaseModel):
    alpha_to_quotes: bool = False
    inventory_penalty: bool = False
    fees: bool = True
    fill_uncertainty: bool = False
    latency_stress_test: bool = False
    adverse_selection_measurement: bool = False


class OutputsSpec(BaseModel):
    figures_target: int = 6
    tables_target: int = 4
    resume_bullets: int = 2
    interview_questions_target: int = 30


class ProjectSpec(BaseModel):
    """The full structured spec (section 8) that drives code generation.
    This is what `init-project` and the orchestrator consume."""

    project: ProjectMeta
    research_question: str
    hypothesis: Hypothesis
    data: DataSpec
    features: list[str] = Field(default_factory=list)
    models: ModelLadder
    validation: ValidationSpec = Field(default_factory=ValidationSpec)
    trading: TradingSpec = Field(default_factory=TradingSpec)
    robustness: list[str] = Field(default_factory=list)
    outputs: OutputsSpec = Field(default_factory=OutputsSpec)

    # Section 28: how project scope and interview prep split the work.
    project_covers: list[str] = Field(default_factory=list)
    project_does_not_cover: list[str] = Field(default_factory=list)
    separate_interview_prep: list[str] = Field(default_factory=list)
