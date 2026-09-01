"""Research orchestrator (section 25 pseudocode).

Wires registry.get_data_adapter -> get_feature_builder ->
validation.leakage -> experiments.run_walk_forward_experiment -> a
Strategy -> robustness checks, driven by `qpf run --stage ...`.

Every dependency (adapter/feature_builder/target_builder/strategy/
validator) can be overridden explicitly rather than resolved from the
registry — this is what lets tests run the whole pipeline against
`SyntheticMicrostructureAdapter` without touching the real Bybit adapter
or global registry state, while `qpf run` (no overrides) uses the
registered production pieces.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import pandas as pd

from project_factory import registry
from project_factory.experiments import run_walk_forward_experiment, save_experiments
from project_factory.models.factory import build_model
from project_factory.schemas import ProjectSpec
from project_factory.validation.leakage import audit_leakage, safe_feature_columns
from project_factory.validation.walk_forward import WalkForwardValidator

PROJECTS_ROOT = Path(__file__).resolve().parent.parent / "projects"
STAGES = ["data", "models", "trading", "robustness"]


def run_stage(
    spec: ProjectSpec,
    stage: str | None = None,
    all_stages: bool = False,
    resume: bool = True,
    data_adapter=None,
    feature_builder=None,
    target_builder: Callable[[pd.DataFrame], pd.Series] | None = None,
    strategy=None,
    validator: WalkForwardValidator | None = None,
    project_dir: Path | None = None,
    task_type: str | None = None,
    synthetic: bool = False,
) -> dict:
    stages = STAGES if all_stages else [stage]
    if not all_stages and stage not in STAGES:
        raise ValueError(f"unknown stage {stage!r}, must be one of {STAGES}")

    archetype = spec.project.archetype
    data_adapter = data_adapter or registry.get_data_adapter(archetype, synthetic=synthetic)
    feature_builder = feature_builder or registry.get_feature_builder(archetype)
    strategy = strategy or registry.get_strategy(archetype)
    task_type = task_type or registry.get_task_type(archetype)
    validator = validator or WalkForwardValidator(n_train=500, n_test=200)
    project_dir = project_dir or (PROJECTS_ROOT / spec.project.project_id)

    results: dict = {}
    processed_path = project_dir / "data" / "processed" / "market_data.parquet"
    data_quality_path = project_dir / "reports" / "data_quality.json"

    if "data" in stages:
        if resume and processed_path.exists() and data_quality_path.exists():
            results["data_quality"] = json.loads(data_quality_path.read_text())
        else:
            raw_df = data_adapter.load(spec)
            quality_report = data_adapter.validate(raw_df, spec)
            processed_path.parent.mkdir(parents=True, exist_ok=True)
            raw_df.to_parquet(processed_path)
            results["data_quality"] = quality_report.model_dump()
            _write_json(data_quality_path, results["data_quality"])

    needs_features = {"models", "trading", "robustness"} & set(stages)
    if needs_features:
        if not processed_path.exists():
            raise FileNotFoundError(f"{processed_path} not found — run the 'data' stage first")
        raw_df = pd.read_parquet(processed_path)
        features_df = feature_builder.transform(raw_df, spec)
        manifest = feature_builder.feature_manifest()
        audit = audit_leakage(features_df, manifest, decision_time_column="decision_time")
        safe_cols = safe_feature_columns(manifest, audit)
        results["leakage_audit"] = audit.model_dump()

        target_builder = target_builder or registry.get_target_builder(archetype)
        y_full = target_builder(features_df)
        valid_mask = y_full.notna()

        X = features_df.loc[valid_mask, safe_cols].reset_index(drop=True)
        y = y_full.loc[valid_mask].reset_index(drop=True)
        timestamps = features_df.loc[valid_mask, "timestamp"].reset_index(drop=True)
        market_state = features_df.loc[valid_mask].reset_index(drop=True)

    if "models" in stages:
        experiments_dir = project_dir / "reports"
        experiments_dir.mkdir(parents=True, exist_ok=True)
        all_records = []
        skipped_models = []
        for model_name in list(spec.models.baseline) + list(spec.models.predictive):
            try:
                build_model(model_name, task_type=task_type)  # validate the name resolves before running folds
            except ValueError:
                skipped_models.append(model_name)
                continue
            model_factory = lambda name=model_name: build_model(name, task_type=task_type)  # noqa: E731
            records = run_walk_forward_experiment(
                X, y, timestamps, model_factory, validator,
                project_id=spec.project.project_id, model_name=model_name,
            )
            save_experiments(records, experiments_dir / f"{model_name}_experiments.jsonl")
            all_records.extend(records)
        results["experiments"] = [r.model_dump() for r in all_records]
        results["skipped_models"] = skipped_models

    if "trading" in stages:
        model_name = spec.models.predictive[-1] if spec.models.predictive else spec.models.baseline[-1]
        if not _model_resolves(model_name, task_type):
            model_name = _default_model_name(task_type)
        model = build_model(model_name, task_type=task_type)

        split = int(len(X) * 0.7)
        model.fit(X.iloc[:split], y.iloc[:split])
        test_X = X.iloc[split:].reset_index(drop=True)
        test_market = market_state.iloc[split:].reset_index(drop=True)
        predictions = pd.Series(model.predict(test_X))

        decisions = strategy.decisions(predictions, test_market, spec)
        results["trading"] = strategy.evaluate(decisions, test_market, spec)
        _write_json(project_dir / "reports" / "trading_results.json", results["trading"])

    if "robustness" in stages:
        results["robustness"] = _run_robustness_suite(spec, strategy, X, y, market_state, task_type)
        _write_json(project_dir / "reports" / "robustness_results.json", results["robustness"])

    return results


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str))


def _model_resolves(name: str, task_type: str) -> bool:
    try:
        build_model(name, task_type=task_type)
        return True
    except ValueError:
        return False


def _default_model_name(task_type: str) -> str:
    """Fallback model when a spec's own model-ladder name doesn't
    resolve (e.g. an archetype config lists a name the factory doesn't
    know yet) — picks a sane default FOR THE TASK TYPE rather than a
    single hardcoded name, so this stays correct for a regression
    archetype and a classification archetype alike."""
    return "ridge" if task_type == "regression" else "logistic_regression"


def _run_robustness_suite(
    spec: ProjectSpec,
    strategy,
    X: pd.DataFrame,
    y: pd.Series,
    market_state: pd.DataFrame,
    task_type: str,
) -> dict:
    """Archetype-agnostic robustness sweep: reconstructs the SAME
    strategy CLASS (`type(strategy)`) with the SAME current parameters
    (introspected from the instance, not a hardcoded per-archetype
    parameter list) except the one being swept. A parameter is swept
    only if the strategy instance actually has it — e.g. fee_bps exists
    on every strategy built so far, so fee_sensitivity always runs;
    latency_ticks only exists on quote-based strategies (market making),
    so it's skipped for a periodic signal-based strategy (power) rather
    than forced into an economically meaningless "latency" for it.

    Covers what section 6 Archetype B names explicitly (fee_sensitivity,
    latency_sensitivity); volatility_regimes/spread_regimes/
    feature_ablation/model_drift/fill_model_sensitivity are available via
    FailureAnalyzer methods a project can call directly (diagnostics/
    failure_cases.py) but aren't auto-run here — a full sweep over all of
    them is expensive and out of scope for this pass; see
    IMPLEMENTATION_STATUS.md."""
    model_name = spec.models.predictive[-1] if spec.models.predictive else spec.models.baseline[-1]
    if not _model_resolves(model_name, task_type):
        model_name = _default_model_name(task_type)
    model = build_model(model_name, task_type=task_type)
    split = int(len(X) * 0.7)
    model.fit(X.iloc[:split], y.iloc[:split])
    test_X = X.iloc[split:].reset_index(drop=True)
    test_market = market_state.iloc[split:].reset_index(drop=True)
    predictions = pd.Series(model.predict(test_X))

    strategy_cls = type(strategy)
    base_kwargs = {k: v for k, v in vars(strategy).items() if not k.startswith("_")}
    results: dict = {}

    if "fee_bps" in base_kwargs:
        base_fee = base_kwargs["fee_bps"]
        fee_sensitivity = []
        for multiplier in (0.0, 1.0, 5.0, 10.0):
            kwargs = {**base_kwargs, "fee_bps": base_fee * multiplier}
            s = strategy_cls(**kwargs)
            decisions = s.decisions(predictions, test_market, spec)
            result = s.evaluate(decisions, test_market, spec)
            fee_sensitivity.append(
                {"fee_bps": kwargs["fee_bps"], "total_pnl": result["total_pnl"], "sharpe": result["sharpe"]}
            )
        results["fee_sensitivity"] = fee_sensitivity

    if "latency_ticks" in base_kwargs:
        latency_sensitivity = []
        for latency_ticks in (0.0, 1.0, 3.0, 5.0):
            kwargs = {**base_kwargs, "latency_ticks": latency_ticks}
            s = strategy_cls(**kwargs)
            decisions = s.decisions(predictions, test_market, spec)
            result = s.evaluate(decisions, test_market, spec)
            latency_sensitivity.append(
                {"latency_ticks": latency_ticks, "total_pnl": result["total_pnl"], "fill_rate": result["fill_rate"]}
            )
        results["latency_sensitivity"] = latency_sensitivity

    return results
