from pathlib import Path

from project_factory.jd_parser import parse_role
from project_factory.schemas import RoleInput

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def _load_role_input(jd_name: str, call_name: str, firm: str, role: str) -> RoleInput:
    return RoleInput(
        firm_name=firm,
        role_title=role,
        job_description=(EXAMPLES / jd_name).read_text(),
        insider_call_notes=(EXAMPLES / call_name).read_text(),
    )


def test_headlands_scores_microstructure_and_systematic_high():
    role_input = _load_role_input(
        "headlands_jd.txt", "headlands_call.txt", "Headlands Technologies", "Quantitative Researcher"
    )
    analysis = parse_role(role_input)

    assert analysis.signals.electronic_market_microstructure >= 4
    assert analysis.signals.systematic_delta_one >= 4
    assert analysis.signals.power_grid_specificity == 0
    assert analysis.signals.natural_gas_specificity == 0
    assert "futures" in analysis.asset_classes
    assert analysis.systematic_vs_discretionary == "systematic"


def test_headlands_flags_anecdotal_call_note():
    role_input = _load_role_input(
        "headlands_jd.txt", "headlands_call.txt", "Headlands Technologies", "Quantitative Researcher"
    )
    analysis = parse_role(role_input)

    assert analysis.notes_vs_jd_discrepancies, "should flag the 'this person's opinion' sentence"
    assert any("opinion" in d.lower() or "forecast" in d.lower() for d in analysis.notes_vs_jd_discrepancies)


def test_cci_scores_power_grid_high():
    role_input = _load_role_input(
        "cci_jd.txt", "cci_call.txt", "Castleton Commodities International", "Quantitative Analyst, Power & Energy"
    )
    analysis = parse_role(role_input)

    assert analysis.signals.power_grid_specificity >= 4
    assert analysis.signals.electronic_market_microstructure < 4
    assert "power" in analysis.asset_classes


def test_matched_keywords_are_traceable():
    role_input = _load_role_input(
        "headlands_jd.txt", "headlands_call.txt", "Headlands Technologies", "Quantitative Researcher"
    )
    analysis = parse_role(role_input)

    assert "order book" in analysis.matched_keywords["electronic_market_microstructure"]


def test_missing_call_notes_does_not_crash():
    role_input = RoleInput(
        firm_name="Test Firm",
        role_title="Test Role",
        job_description="A basic job description with no special keywords.",
    )
    analysis = parse_role(role_input)
    assert analysis.notes_vs_jd_discrepancies == []
