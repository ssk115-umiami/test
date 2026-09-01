from pathlib import Path

import pytest

from project_factory.data.adapters.synthetic_power import SyntheticPowerDataAdapter
from project_factory.features.power import PowerFeatureBuilder
from project_factory.features.power import build_target as build_power_target
from project_factory.jd_parser import parse_role
from project_factory.orchestrator import run_stage
from project_factory.router import route_archetype
from project_factory.schemas import CandidateConfig, RoleInput
from project_factory.spec_builder import build_project_spec
from project_factory.trading.no_trade_sizing import NoTradeSizingStrategy
from project_factory.validation.walk_forward import WalkForwardValidator

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def _cci_spec():
    role_input = RoleInput(
        firm_name="Castleton Commodities International",
        role_title="Quantitative Analyst, Power & Energy",
        job_description=(EXAMPLES / "cci_jd.txt").read_text(),
        insider_call_notes=(EXAMPLES / "cci_call.txt").read_text(),
    )
    analysis = parse_role(role_input)
    routing = route_archetype(analysis)
    return build_project_spec(analysis, routing, CandidateConfig())


@pytest.fixture
def pipeline_kwargs(tmp_path):
    return dict(
        data_adapter=SyntheticPowerDataAdapter(n_hours=24 * 60, seed=2, cache_dir=tmp_path / "raw"),
        feature_builder=PowerFeatureBuilder(spread_lag_hours=1, rolling_window_hours=24),
        target_builder=build_power_target,
        strategy=NoTradeSizingStrategy(no_trade_threshold=1.0, fee_bps=2.0),
        validator=WalkForwardValidator(n_train=24 * 20, n_test=24 * 5),
        project_dir=tmp_path / "project",
        task_type="regression",
    )


def test_power_pipeline_runs_all_stages_end_to_end(pipeline_kwargs):
    spec = _cci_spec()
    assert spec.project.archetype.value == "power_da_rt"

    data_results = run_stage(spec, stage="data", resume=False, **pipeline_kwargs)
    assert data_results["data_quality"]["n_rows"] == 24 * 60

    models_results = run_stage(spec, stage="models", resume=True, **pipeline_kwargs)
    assert models_results["leakage_audit"]["passed"] is True
    assert len(models_results["experiments"]) > 0
    assert all("rmse" in r["predictive_metrics"] for r in models_results["experiments"])

    trading_results = run_stage(spec, stage="trading", resume=True, **pipeline_kwargs)
    trading = trading_results["trading"]
    assert {"total_pnl", "sharpe", "max_drawdown", "fill_rate", "turnover"}.issubset(trading)

    robustness_results = run_stage(spec, stage="robustness", resume=True, **pipeline_kwargs)
    assert len(robustness_results["robustness"]["fee_sensitivity"]) == 4


def test_power_pipeline_via_all_stages_flag(pipeline_kwargs):
    spec = _cci_spec()
    results = run_stage(spec, all_stages=True, resume=False, **pipeline_kwargs)
    assert "data_quality" in results
    assert "experiments" in results
    assert "trading" in results
    assert "robustness" in results


def test_same_orchestrator_code_serves_both_archetypes_without_branching():
    """The generalization test: orchestrator.py must contain no
    archetype-specific conditionals — everything per-archetype comes
    from registry lookups / injected dependencies."""
    import inspect

    import project_factory.orchestrator as orchestrator_module

    source = inspect.getsource(orchestrator_module)
    for forbidden in ["predictive_market_making", "power_da_rt", "Archetype.PREDICTIVE", "Archetype.POWER"]:
        assert forbidden not in source, f"orchestrator.py should not special-case {forbidden!r}"
