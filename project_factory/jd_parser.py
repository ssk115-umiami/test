"""Deterministic JD + insider-call-notes parser (sections 3.1, 3.2, 6.1).

Turns free text into a structured RoleAnalysis: signal scores across the
17 routing dimensions (section 7), plus asset-class / frequency / language
hints and a list of anecdotal claims from the call notes that should be
flagged rather than silently trusted over the official JD (section 3.2).

This is intentionally a transparent keyword/heuristic scorer, not an LLM
call: `qpf analyze-role` must be reproducible and testable without an API
key, and every score should be traceable to the phrases that produced it
(see `matched_keywords` on RoleAnalysis). An LLM-assisted refinement pass
can be layered on top later (section 23) without changing this contract.
"""

from __future__ import annotations

import re

from project_factory.schemas import RoleAnalysis, RoleInput, SignalScores

# --------------------------------------------------------------------------
# Keyword lexicon: dimension -> phrases that count as evidence.
# Phrases are matched case-insensitively as substrings/word-boundaries.
# --------------------------------------------------------------------------

SIGNAL_LEXICON: dict[str, list[str]] = {
    "electronic_market_microstructure": [
        "order book", "limit order", "l2 data", "level 2", "quoting",
        "microstructure", "adverse selection", "market making",
        "market maker", "bid-ask", "bid/ask", "tick data", "fills",
        "fill rate", "spread capture",
    ],
    "physical_commodity_knowledge": [
        "physical commodity", "physical power", "physical gas",
        "merchant energy", "warehouse", "physical grid", "pipeline",
        "freight", "logistics", "outage data", "generation data",
        "physical market",
    ],
    "power_grid_specificity": [
        "power grid", "grid operations", "day-ahead", "real-time price",
        "nyiso", "pjm", "ercot", "iso market", "lbmp", "congestion",
        "load forecast", "power trading", "power desk", "generation data",
        "generation mix", "generation outage", "power generation",
        "unit commitment",
    ],
    "natural_gas_specificity": [
        "natural gas", "henry hub", "pipeline flows", "gas trading",
        "gas desk", "storage level", "heating degree day", "basis",
    ],
    "options_volatility": [
        "options", "implied volatility", "vol surface", "greeks",
        "delta hedg", "gamma", "vega", "volatility desk", "black-scholes",
    ],
    "cross_sectional_equities": [
        "equity", "equities", "stat arb", "statistical arbitrage",
        "factor model", "cross-sectional", "long/short equity",
        "universe of stocks",
    ],
    "systematic_delta_one": [
        "systematic", "fully automated", "delta-one", "delta one",
        "no discretionary", "software makes every trade", "futures",
        "proprietary trading", "algorithmic trading",
    ],
    "time_series_ml": [
        "time series", "time-series", "neural network", "machine learning",
        "predictive signal", "predictive model", "forecast", "backtest",
    ],
    "neural_network_emphasis": [
        "neural network", "deep learning", "neural-network",
    ],
    "statistics_emphasis": [
        "statistics", "statistical", "regression", "probability",
        "hypothesis", "dataframe", "data-generating process",
        "distribution",
    ],
    "linear_algebra_emphasis": [
        "linear algebra", "eigenvalue", "eigenvector", "svd",
        "singular value", "matrix", "rank", "positive-definite",
        "conditioning", "multicollinearity", "regularization",
        "ridge", "lasso",
    ],
    "coding_interview_emphasis": [
        "leetcode", "algorithm", "data structures", "coding round",
        "technical coding", "whiteboard", "programming ability",
    ],
    "production_software_emphasis": [
        "production", "productioniz", "deploy", "maintainable",
        "software architecture", "codebase", "engineering team",
        "research pipeline", "pipeline code",
    ],
    "execution_emphasis": [
        "execution", "latency", "fills", "quoting", "order routing",
        "market impact", "slippage",
    ],
    "pnl_ownership": [
        "pnl", "p&l", "profit and loss", "strategy performance",
        "measurable strategy pnl", "own a research idea",
        "trading decisions",
    ],
    "fundamental_market_reasoning": [
        "fundamental", "physical/causal", "physical causal",
        "weather driver", "supply/demand", "supply and demand",
        "market intuition", "grid conditions", "causal intuition",
    ],
    "low_frequency_commercial": [
        "commercial", "merchant", "case study", "desk-facing",
        "trading and risk decisions", "risk managers", "commercial decision",
    ],
}

ASSET_CLASS_LEXICON: dict[str, list[str]] = {
    "power": ["power", "power grid", "power trading", "nyiso", "pjm", "ercot", "lbmp", "power desk"],
    "natural_gas": ["natural gas", "henry hub", "gas trading", "gas desk"],
    "futures": ["futures"],
    "equities": ["equities", "equity", "stocks"],
    "options": ["options", "implied volatility", "vol surface"],
    "metals": ["metals", "lme", "comex", "copper"],
    "crude_and_products": ["crude", "wti", "brent", "refined products", "crack spread"],
    "crypto": ["crypto", "bitcoin", "ethereum"],
    "fixed_income": ["bonds", "fixed income", "rates"],
}

FREQUENCY_LEXICON: dict[str, list[str]] = {
    "subsecond_or_tick": ["subsecond", "sub-second", "tick data", "high-frequency", "order book"],
    "intraday": ["intraday", "minute bar"],
    "hourly": ["hourly", "day-ahead", "real-time price"],
    "daily": ["daily"],
}

LANGUAGE_LEXICON: list[str] = ["python", "c++", "java", "sql", "matlab", "scala"]

SYSTEMATIC_MARKERS = ["systematic", "fully automated", "no discretionary", "software makes every trade"]
DISCRETIONARY_MARKERS = ["discretionary trader", "discretionary trading", "trader intuition drives"]

TRADING_MARKERS = ["trading desk", "trading decisions", "position", "quoting", "pnl"]
RESEARCH_MARKERS = ["research", "backtest", "hypothesis", "model"]
EXECUTION_MARKERS = ["execution", "fills", "order routing", "latency"]

ANECDOTE_MARKERS = [
    "this person's opinion", "not confirmed", "one person's forecast",
    "not a hiring requirement", "anecdote", "their belief", "believe",
]


def _find_matches(text: str, phrases: list[str]) -> list[str]:
    """Word-boundary match so generic short words (e.g. 'power', a bare
    'generation') don't fire on unrelated compounds like 'powerful' or
    'research-generation'."""
    lowered = text.lower()
    hits = []
    for phrase in phrases:
        # Custom (not \b) boundary: \b fails to match after a symbol like
        # the '+' in "c++" (symbol -> whitespace isn't a \w/\W transition).
        # Require the phrase not be glued to an alphanumeric on either side.
        pattern = r"(?<![A-Za-z0-9])" + re.escape(phrase.lower()) + r"(?![A-Za-z0-9])"
        if re.search(pattern, lowered):
            hits.append(phrase)
    return hits


def _score_from_matches(n_matches: int) -> int:
    """Map a raw keyword-hit count to a 0-5 score. Diminishing returns
    past a handful of distinct hits — this is a coverage signal, not a
    word-frequency count."""
    return min(5, n_matches)


def score_signals(text: str) -> tuple[SignalScores, dict[str, list[str]]]:
    matched: dict[str, list[str]] = {}
    scores: dict[str, int] = {}
    for dim, phrases in SIGNAL_LEXICON.items():
        hits = _find_matches(text, phrases)
        matched[dim] = hits
        scores[dim] = _score_from_matches(len(hits))
    return SignalScores(**scores), matched


def _extract_list(text: str, lexicon: dict[str, list[str]]) -> list[str]:
    return [key for key, phrases in lexicon.items() if _find_matches(text, phrases)]


def _classify_systematic_vs_discretionary(text: str) -> str:
    lowered = text.lower()
    systematic = any(m in lowered for m in SYSTEMATIC_MARKERS)
    discretionary = any(m in lowered for m in DISCRETIONARY_MARKERS)
    if systematic and not discretionary:
        return "systematic"
    if discretionary and not systematic:
        return "discretionary"
    if systematic and discretionary:
        return "hybrid"
    return "unclear"


def _classify_focus(text: str) -> list[str]:
    lowered = text.lower()
    focus = []
    if any(m in lowered for m in TRADING_MARKERS):
        focus.append("trading")
    if any(m in lowered for m in RESEARCH_MARKERS):
        focus.append("research")
    if any(m in lowered for m in EXECUTION_MARKERS):
        focus.append("execution")
    return focus or ["unclear"]


def _extract_discrepancies(call_notes: str) -> list[str]:
    """Section 3.2: flag anecdotal/opinion claims in the call notes so they
    don't silently override the official JD requirements."""
    if not call_notes:
        return []
    sentences = re.split(r"(?<=[.!?])\s+", call_notes.replace("\n", " "))
    flagged = []
    for sentence in sentences:
        lowered = sentence.lower()
        if any(marker in lowered for marker in ANECDOTE_MARKERS):
            flagged.append(sentence.strip())
    return flagged


def parse_role(role_input: RoleInput) -> RoleAnalysis:
    jd = role_input.job_description or ""
    call = role_input.insider_call_notes or ""
    combined = f"{jd}\n{call}"

    signals, matched_keywords = score_signals(combined)

    return RoleAnalysis(
        role_input=role_input,
        signals=signals,
        asset_classes=_extract_list(combined, ASSET_CLASS_LEXICON),
        systematic_vs_discretionary=_classify_systematic_vs_discretionary(combined),
        trading_vs_research_vs_execution=_classify_focus(combined),
        data_frequency_hints=_extract_list(combined, FREQUENCY_LEXICON),
        languages_mentioned=_find_matches(combined, LANGUAGE_LEXICON),
        matched_keywords=matched_keywords,
        notes_vs_jd_discrepancies=_extract_discrepancies(call),
    )
