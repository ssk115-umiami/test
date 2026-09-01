"""Archetype router (section 7).

Deterministic, rule-based routing from RoleAnalysis signal scores to a
primary/secondary Archetype. The explicit ordered rules mirror section 7
of the handoff spec exactly; an `archetype_scores` map (continuous, not
just the winning rule) is also returned so a secondary archetype and a
routing_confidence can be derived without a second pass.

An LLM-assisted refinement layer could sit in front of this (section 23)
to pre-digest messier JD text, but the rule evaluation itself stays
deterministic so `analyze-role` is reproducible.
"""

from __future__ import annotations

from project_factory.registry import get_archetype_config
from project_factory.schemas import Archetype, RoleAnalysis, RoutingResult

# Weights used to build a continuous score per archetype (for secondary
# selection + confidence), independent of the discrete section-7 rules
# below, which decide the primary pick.
_ARCHETYPE_SIGNAL_WEIGHTS: dict[Archetype, dict[str, float]] = {
    Archetype.PREDICTIVE_MARKET_MAKING: {
        "electronic_market_microstructure": 2.0,
        "systematic_delta_one": 1.0,
        "execution_emphasis": 1.0,
        "production_software_emphasis": 0.5,
    },
    Archetype.POWER_DA_RT: {
        "power_grid_specificity": 2.0,
        "physical_commodity_knowledge": 1.0,
        "fundamental_market_reasoning": 1.0,
    },
    Archetype.GAS_BASIS: {
        "natural_gas_specificity": 2.0,
        "physical_commodity_knowledge": 1.0,
        "fundamental_market_reasoning": 1.0,
    },
    Archetype.OPTIONS_MARKET_MAKING: {
        "options_volatility": 2.0,
    },
    Archetype.STAT_ARB: {
        "cross_sectional_equities": 2.0,
        "statistics_emphasis": 1.0,
    },
    Archetype.SYSTEMATIC_FUTURES: {
        "systematic_delta_one": 2.0,
        "time_series_ml": 1.0,
        "statistics_emphasis": 1.0,
    },
    Archetype.PHYSICAL_COMMODITY: {
        "low_frequency_commercial": 2.0,
        "physical_commodity_knowledge": 1.0,
        "fundamental_market_reasoning": 1.0,
    },
}


def _archetype_scores(analysis: RoleAnalysis) -> dict[Archetype, float]:
    scores: dict[Archetype, float] = {}
    for archetype, weights in _ARCHETYPE_SIGNAL_WEIGHTS.items():
        raw = sum(analysis.signals.get(dim) * w for dim, w in weights.items())
        max_possible = sum(5 * w for w in weights.values())
        scores[archetype] = round(raw / max_possible, 3) if max_possible else 0.0
    return scores


def _power_mentioned_repeatedly(analysis: RoleAnalysis) -> bool:
    text = (analysis.role_input.job_description or "") + " " + (
        analysis.role_input.insider_call_notes or ""
    )
    return text.lower().count("power") >= 3


def _select_primary(analysis: RoleAnalysis) -> tuple[Archetype, str]:
    """Evaluate the section-7 rules in the documented order. Returns the
    first matching archetype and the plain-language reason it fired."""
    s = analysis.signals

    if s.electronic_market_microstructure >= 4 and s.systematic_delta_one >= 4:
        return (
            Archetype.PREDICTIVE_MARKET_MAKING,
            "electronic_market_microstructure >= 4 and systematic_delta_one >= 4",
        )

    if s.power_grid_specificity >= 4 or (
        s.physical_commodity_knowledge >= 3 and _power_mentioned_repeatedly(analysis)
    ):
        return (
            Archetype.POWER_DA_RT,
            (
                "power_grid_specificity >= 4, or physical_commodity_knowledge >= 3 "
                "with 'power' mentioned repeatedly"
            ),
        )

    if s.natural_gas_specificity >= 4:
        return Archetype.GAS_BASIS, "natural_gas_specificity >= 4"

    if s.options_volatility >= 4:
        return Archetype.OPTIONS_MARKET_MAKING, "options_volatility >= 4"

    if s.cross_sectional_equities >= 4:
        return Archetype.STAT_ARB, "cross_sectional_equities >= 4"

    no_dominant_signal = (
        s.electronic_market_microstructure < 4
        and s.power_grid_specificity < 4
        and s.options_volatility < 4
    )
    if s.systematic_delta_one >= 3 and no_dominant_signal:
        return (
            Archetype.SYSTEMATIC_FUTURES,
            "systematic_delta_one >= 3 with no dominant microstructure/power/options signal",
        )

    if s.low_frequency_commercial >= 3 and (
        s.physical_commodity_knowledge >= 3 or "metals" in analysis.asset_classes
        or "crude_and_products" in analysis.asset_classes
    ):
        return (
            Archetype.PHYSICAL_COMMODITY,
            "low_frequency_commercial >= 3 with metals/oil/physical language dominant",
        )

    # Fallback: no explicit rule fired. Pick the highest continuous score
    # rather than leaving routing undefined.
    scores = _archetype_scores(analysis)
    best = max(scores, key=lambda a: scores[a])
    return best, f"no explicit rule fired; highest continuous signal score ({scores[best]})"


def route_archetype(analysis: RoleAnalysis) -> RoutingResult:
    primary, reason = _select_primary(analysis)
    scores = _archetype_scores(analysis)

    remaining = {a: v for a, v in scores.items() if a != primary}
    secondary = max(remaining, key=lambda a: remaining[a]) if remaining else None
    if secondary is not None and remaining[secondary] < 0.15:
        secondary = None

    primary_config = get_archetype_config(primary)
    confidence = max(scores.get(primary, 0.0), 0.5)
    confidence = min(confidence, 1.0)

    why_primary_matches = [reason]
    top_matched = sorted(
        (
            (dim, kws)
            for dim, kws in analysis.matched_keywords.items()
            if kws and dim in _ARCHETYPE_SIGNAL_WEIGHTS.get(primary, {})
        ),
        key=lambda item: -len(item[1]),
    )
    for dim, kws in top_matched[:4]:
        why_primary_matches.append(f"{dim}: matched {kws}")

    interview_gap = list(primary_config.separate_interview_prep)
    if secondary is not None:
        secondary_config = get_archetype_config(secondary)
        gap_note = (
            f"secondary archetype '{secondary.value}' scored "
            f"{remaining[secondary]:.2f}; consider covering "
            f"{secondary_config.canonical_title!r} themes in interview prep "
            "if this firm/role leans that direction too."
        )
        interview_gap.append(gap_note)

    return RoutingResult(
        primary_archetype=primary,
        secondary_archetype=secondary,
        routing_confidence=confidence,
        why_primary_matches=why_primary_matches,
        what_primary_does_not_cover=list(primary_config.project_does_not_cover),
        interview_prep_needed_to_cover_gap=interview_gap,
        archetype_scores={a.value: v for a, v in scores.items()},
    )
