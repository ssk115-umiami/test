from pathlib import Path

from project_factory.jd_parser import parse_role
from project_factory.router import route_archetype
from project_factory.schemas import Archetype, CandidateConfig, RoleInput
from project_factory.spec_builder import build_project_spec

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def _build_spec(jd_name: str, call_name: str, firm: str, role: str):
    role_input = RoleInput(
        firm_name=firm,
        role_title=role,
        job_description=(EXAMPLES / jd_name).read_text(),
        insider_call_notes=(EXAMPLES / call_name).read_text(),
    )
    analysis = parse_role(role_input)
    routing = route_archetype(analysis)
    return build_project_spec(analysis, routing, CandidateConfig())


def test_headlands_spec_matches_archetype():
    spec = _build_spec("headlands_jd.txt", "headlands_call.txt", "Headlands Technologies", "Quantitative Researcher")

    assert spec.project.archetype == Archetype.PREDICTIVE_MARKET_MAKING
    assert spec.project.project_id == "headlands_technologies_quantitative_researcher_predictive_market_making_v1"
    assert spec.trading.alpha_to_quotes is True
    assert spec.trading.inventory_penalty is True
    assert spec.validation.random_kfold_allowed is False
    assert "logistic_regression" in spec.models.predictive
    assert spec.project_covers
    assert spec.project_does_not_cover


def test_spec_round_trips_through_yaml():
    import yaml

    from project_factory.schemas import ProjectSpec

    spec = _build_spec(
        "cci_jd.txt", "cci_call.txt", "Castleton Commodities International", "Quantitative Analyst, Power & Energy"
    )
    dumped = yaml.safe_dump(spec.model_dump(mode="json"), sort_keys=False)
    reloaded = ProjectSpec.model_validate(yaml.safe_load(dumped))
    assert reloaded == spec
