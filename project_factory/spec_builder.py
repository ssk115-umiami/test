"""Build a ProjectSpec (section 8) from a RoleAnalysis + RoutingResult.

The archetype's canonical config (configs/archetypes/*.yaml) supplies the
reusable defaults (canonical research question, data/feature/model/trading
templates, robustness suite, project_covers/does_not_cover/interview_prep);
this module fills in the firm/role-specific identity on top of it.
"""

from __future__ import annotations

import re

from project_factory.registry import get_archetype_config
from project_factory.schemas import (
    CandidateConfig,
    DataSpec,
    Hypothesis,
    ModelLadder,
    OutputsSpec,
    ProjectMeta,
    ProjectSpec,
    RoleAnalysis,
    RoutingResult,
    TradingSpec,
    ValidationSpec,
)


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return re.sub(r"_+", "_", slug)


def build_project_spec(
    role_analysis: RoleAnalysis,
    routing: RoutingResult,
    candidate: CandidateConfig,
) -> ProjectSpec:
    archetype = routing.primary_archetype
    config = get_archetype_config(archetype)
    role_input = role_analysis.role_input

    firm_slug = _slugify(role_input.firm_name)
    role_slug = _slugify(role_input.role_title)
    project_id = f"{firm_slug}_{role_slug}_{archetype.value}_v1"

    meta = ProjectMeta(
        project_id=project_id,
        firm=role_input.firm_name,
        role=role_input.role_title,
        archetype=archetype,
        title=config.canonical_title,
    )

    hypothesis = Hypothesis(
        economic=config.economic_hypothesis,
        statistical=config.statistical_hypothesis,
    )

    data = DataSpec(**config.data.model_dump())
    models = ModelLadder(**config.models.model_dump())
    trading = TradingSpec(**config.trading.model_dump())

    project_covers = list(config.project_covers)
    project_does_not_cover = list(routing.what_primary_does_not_cover)
    separate_interview_prep = list(routing.interview_prep_needed_to_cover_gap)

    return ProjectSpec(
        project=meta,
        research_question=config.canonical_research_question,
        hypothesis=hypothesis,
        data=data,
        features=list(config.features),
        models=models,
        validation=ValidationSpec(),
        trading=trading,
        robustness=list(config.robustness),
        outputs=OutputsSpec(),
        project_covers=project_covers,
        project_does_not_cover=project_does_not_cover,
        separate_interview_prep=separate_interview_prep,
    )
