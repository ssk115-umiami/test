from pathlib import Path

from project_factory.jd_parser import parse_role
from project_factory.router import route_archetype
from project_factory.schemas import Archetype, RoleInput

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def _analyze(jd_name: str, call_name: str, firm: str, role: str):
    role_input = RoleInput(
        firm_name=firm,
        role_title=role,
        job_description=(EXAMPLES / jd_name).read_text(),
        insider_call_notes=(EXAMPLES / call_name).read_text(),
    )
    return parse_role(role_input)


def test_headlands_routes_to_predictive_market_making():
    """Section 24's acceptance test: the Headlands fixture must
    deterministically produce primary=predictive_market_making,
    secondary=systematic_futures."""
    analysis = _analyze("headlands_jd.txt", "headlands_call.txt", "Headlands Technologies", "Quantitative Researcher")
    routing = route_archetype(analysis)

    assert routing.primary_archetype == Archetype.PREDICTIVE_MARKET_MAKING
    assert routing.secondary_archetype == Archetype.SYSTEMATIC_FUTURES
    assert routing.routing_confidence > 0.5
    assert routing.why_primary_matches
    assert routing.what_primary_does_not_cover
    assert routing.interview_prep_needed_to_cover_gap


def test_cci_routes_to_power_da_rt():
    """Section 18's exemplar: energy/CCI-style JD should route to the
    Power Regime / DA-RT archetype."""
    analysis = _analyze(
        "cci_jd.txt", "cci_call.txt", "Castleton Commodities International", "Quantitative Analyst, Power & Energy"
    )
    routing = route_archetype(analysis)

    assert routing.primary_archetype == Archetype.POWER_DA_RT


def test_routing_is_deterministic():
    analysis = _analyze("headlands_jd.txt", "headlands_call.txt", "Headlands Technologies", "Quantitative Researcher")
    r1 = route_archetype(analysis)
    r2 = route_archetype(analysis)
    assert r1.primary_archetype == r2.primary_archetype
    assert r1.archetype_scores == r2.archetype_scores


def test_routing_never_crashes_on_empty_notes():
    role_input = RoleInput(
        firm_name="Firm",
        role_title="Role",
        job_description="Generic trading role with statistics and probability requirements.",
    )
    analysis = parse_role(role_input)
    routing = route_archetype(analysis)
    assert routing.primary_archetype in list(Archetype)
