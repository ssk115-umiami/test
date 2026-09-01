from pathlib import Path

import pytest

from project_factory.data.adapters.synthetic_microstructure import SyntheticMicrostructureAdapter
from project_factory.features.microstructure import MicrostructureFeatureBuilder, build_target
from project_factory.jd_parser import parse_role
from project_factory.orchestrator import run_stage
from project_factory.router import route_archetype
from project_factory.schemas import CandidateConfig, RoleInput
from project_factory.spec_builder import build_project_spec
from project_factory.trading.signals import MarketMakingStrategy
from project_factory.validation.walk_forward import WalkForwardValidator

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
HORIZON = 3


def _headlands_spec():
    role_input = RoleInput(
        firm_name="Headlands Technologies",
        role_title="Quantitative Researcher",
        job_description=(EXAMPLES / "headlands_jd.txt").read_text(),
        insider_call_notes=(EXAMPLES / "headlands_call.txt").read_text(),
    )
    analysis = parse_role(role_input)
    routing = route_archetype(analysis)
    return build_project_spec(analysis, routing, CandidateConfig())


def _target_builder(df):
    return build_target(df, horizon=HORIZON, threshold=0.0)


@pytest.fixture
def pipeline_kwargs(tmp_path):
    return dict(
        data_adapter=SyntheticMicrostructureAdapter(n_rows=1800, seed=3, signal_strength=1.5, cache_dir=tmp_path / "raw"),
        feature_builder=MicrostructureFeatureBuilder(trailing_window=5),
        target_builder=_target_builder,
        strategy=MarketMakingStrategy(alpha=1.0, gamma=0.05, fee_bps=1.0),
        validator=WalkForwardValidator(n_train=400, n_test=200),
        project_dir=tmp_path / "project",
        task_type="classification",
    )


def test_full_pipeline_runs_all_stages_end_to_end(pipeline_kwargs):
    spec = _headlands_spec()
    # spec.project.archetype is predictive_market_making per the section-24
    # acceptance test — confirmed again here since the trading/target
    # pieces below assume that archetype's classification target shape.
    assert spec.project.archetype.value == "predictive_market_making"

    data_results = run_stage(spec, stage="data", resume=False, **pipeline_kwargs)
    assert "n_rows" in data_results["data_quality"]
    assert data_results["data_quality"]["n_rows"] == 1800

    models_results = run_stage(spec, stage="models", resume=True, **pipeline_kwargs)
    assert models_results["leakage_audit"]["passed"] is True
    assert len(models_results["experiments"]) > 0
    # every experiment record's predictive_metrics should be non-empty
    assert all(r["predictive_metrics"] for r in models_results["experiments"])

    trading_results = run_stage(spec, stage="trading", resume=True, **pipeline_kwargs)
    trading = trading_results["trading"]
    assert set(["total_pnl", "sharpe", "max_drawdown", "fill_rate", "turnover"]).issubset(trading)
    assert 0.0 <= trading["fill_rate"] <= 1.0

    robustness_results = run_stage(spec, stage="robustness", resume=True, **pipeline_kwargs)
    fee_curve = robustness_results["robustness"]["fee_sensitivity"]
    assert len(fee_curve) == 4
    pnls = [row["total_pnl"] for row in fee_curve]
    assert pnls == sorted(pnls, reverse=True), "higher fees (identical fills) must not increase pnl"

    latency_curve = robustness_results["robustness"]["latency_sensitivity"]
    assert len(latency_curve) == 4
    assert all(0.0 <= row["fill_rate"] <= 1.0 for row in latency_curve)


def test_all_stages_flag_runs_every_stage_in_one_call(pipeline_kwargs):
    spec = _headlands_spec()
    results = run_stage(spec, all_stages=True, resume=False, **pipeline_kwargs)
    assert "data_quality" in results
    assert "experiments" in results
    assert "trading" in results
    assert "robustness" in results


def test_models_stage_requires_data_stage_first(pipeline_kwargs):
    spec = _headlands_spec()
    with pytest.raises(FileNotFoundError):
        run_stage(spec, stage="models", resume=True, **pipeline_kwargs)


def test_unknown_stage_raises(pipeline_kwargs):
    spec = _headlands_spec()
    with pytest.raises(ValueError):
        run_stage(spec, stage="not_a_real_stage", **pipeline_kwargs)
