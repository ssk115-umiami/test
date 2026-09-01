"""Reporter (section 11.7): turns experiment/trading/robustness JSON
output already written to `projects/<id>/reports/` into figures, a
model-comparison table, and appended results sections in
RESEARCH_MEMO.md / README.md.

Deliberately lean for this first pass — 3 figures, 1 table, appended
(not intelligently-diffed) memo sections — rather than the fuller
plots.py/tables.py/readme.py/resume.py/interview.py split sketched in
section 9. That split is worth doing once a second archetype's reports
show what's actually shared vs. archetype-specific; right now it would
be speculative structure with one caller.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from project_factory.experiments import load_experiments  # noqa: E402
from project_factory.schemas import ProjectSpec  # noqa: E402

PROJECTS_ROOT = Path(__file__).resolve().parent.parent.parent / "projects"


def _load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _load_all_experiments(reports_dir: Path) -> dict[str, list]:
    by_model: dict[str, list] = {}
    for path in sorted(reports_dir.glob("*_experiments.jsonl")):
        records = load_experiments(path)
        if not records:
            continue
        by_model.setdefault(records[0].model, []).extend(records)
    return by_model


def _build_model_comparison_table(experiments_by_model: dict[str, list]) -> pd.DataFrame:
    rows = []
    for model_name, records in experiments_by_model.items():
        metrics_df = pd.DataFrame([r.predictive_metrics for r in records])
        row = {"model": model_name, "n_folds": len(records)}
        row.update(metrics_df.mean(numeric_only=True).to_dict())
        rows.append(row)
    return pd.DataFrame(rows).sort_values("model").reset_index(drop=True)


def _plot_series(values: list[float], title: str, ylabel: str, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(values)
    ax.set_title(title)
    ax.set_xlabel("step")
    ax.set_ylabel(ylabel)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _plot_sensitivity(rows: list[dict], x_key: str, y_key: str, title: str, path: Path) -> None:
    xs = [r[x_key] for r in rows]
    ys = [r[y_key] for r in rows]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(xs, ys, marker="o")
    ax.set_title(title)
    ax.set_xlabel(x_key)
    ax.set_ylabel(y_key)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _append_results_section(path: Path, heading: str, body: str) -> None:
    if not path.exists():
        return
    existing = path.read_text()
    marker = f"\n## {heading}\n"
    if marker in existing:
        return  # already appended by a previous report run
    path.write_text(existing.rstrip() + "\n" + marker + body + "\n")


def build_reports(spec: ProjectSpec, project_dir: Path | None = None) -> dict:
    project_dir = project_dir or (PROJECTS_ROOT / spec.project.project_id)
    reports_dir = project_dir / "reports"
    figures_dir = reports_dir / "figures"
    tables_dir = reports_dir / "tables"
    figures_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)

    experiments_by_model = _load_all_experiments(reports_dir)
    trading = _load_json(reports_dir / "trading_results.json")
    robustness = _load_json(reports_dir / "robustness_results.json")

    if not experiments_by_model:
        raise FileNotFoundError(
            f"no *_experiments.jsonl files found in {reports_dir} — run the 'models' stage first"
        )

    table = _build_model_comparison_table(experiments_by_model)
    table_path = tables_dir / "model_comparison.csv"
    table.to_csv(table_path, index=False)

    figure_paths = []
    if trading and "equity_curve" in trading:
        path = figures_dir / "equity_curve.png"
        _plot_series(trading["equity_curve"], "Simulated equity curve", "equity", path)
        figure_paths.append(path)
    if trading and "inventory_series" in trading:
        path = figures_dir / "inventory_series.png"
        _plot_series(trading["inventory_series"], "Inventory over time", "inventory (units)", path)
        figure_paths.append(path)
    if robustness and robustness.get("fee_sensitivity"):
        path = figures_dir / "fee_sensitivity.png"
        _plot_sensitivity(robustness["fee_sensitivity"], "fee_bps", "total_pnl", "PnL vs. fee level", path)
        figure_paths.append(path)
    if robustness and robustness.get("latency_sensitivity"):
        path = figures_dir / "latency_sensitivity.png"
        _plot_sensitivity(
            robustness["latency_sensitivity"], "latency_ticks", "fill_rate", "Fill rate vs. latency", path
        )
        figure_paths.append(path)

    memo_body = ["```", table.to_string(index=False), "```", ""]
    if trading:
        memo_body.append(
            f"Trading layer (held-out test split): total_pnl={trading['total_pnl']:.4f}, "
            f"sharpe={trading['sharpe']:.4f}, max_drawdown={trading['max_drawdown']:.4f}, "
            f"fill_rate={trading['fill_rate']:.3f}, turnover={trading['turnover']:.2f}."
        )
    if robustness and robustness.get("fee_sensitivity"):
        pnls = [r["total_pnl"] for r in robustness["fee_sensitivity"]]
        memo_body.append(
            f"Fee sensitivity: total_pnl ranges from {max(pnls):.4f} (lowest fee) to "
            f"{min(pnls):.4f} (highest fee tested) — see fee_sensitivity.png."
        )
    memo_body.append(
        "\nFigures: " + ", ".join(p.name for p in figure_paths) + " (in reports/figures/)."
        if figure_paths
        else ""
    )
    _append_results_section(project_dir / "RESEARCH_MEMO.md", "Results (auto-generated)", "\n".join(memo_body))

    readme_body = table.to_string(index=False)
    if trading:
        readme_body += f"\n\nHeld-out total PnL: {trading['total_pnl']:.4f} (sharpe {trading['sharpe']:.4f})."
    _append_results_section(project_dir / "README.md", "Results", f"```\n{readme_body}\n```")

    return {
        "table": str(table_path),
        "figures": [str(p) for p in figure_paths],
    }
