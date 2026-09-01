"""Project scaffolding (section 5 output contract).

`initialize_project` creates the self-contained
`projects/<project_id>/` folder structure and seeds the recruiting-facing
docs with spec-derived content so they are never empty placeholders.

The full auto-generated Reporter (section 11.7 — figures/tables/memo
built from experiment metadata after a run) lands in Milestone 2/3; this
module only handles the one-time scaffold at `init-project` time.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from project_factory.schemas import ProjectSpec

PROJECTS_ROOT = Path(__file__).resolve().parent.parent / "projects"

SUBDIRS = [
    "config",
    "data/raw",
    "data/interim",
    "data/processed",
    "src",
    "notebooks",
    "tests",
    "reports/figures",
    "reports/tables",
]


def _write_if_absent(path: Path, content: str) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _render_readme(spec: ProjectSpec) -> str:
    return f"""# {spec.project.title}

**Firm:** {spec.project.firm} · **Role:** {spec.project.role} · **Archetype:** {spec.project.archetype.value}

## Research question

{spec.research_question}

## Why this project matches the role

{chr(10).join(f"- {c}" for c in spec.project_covers) or "- (fill in from ROLE_ANALYSIS.md)"}

## What this project does NOT cover

{chr(10).join(f"- {c}" for c in spec.project_does_not_cover) or "- (none identified)"}

See `RESEARCH_MEMO.md` for the full writeup, `INTERVIEW_MASTERY.md` for
defense material, and `ASSUMPTIONS_AND_RISKS.md` for known limitations.

Run with:

```bash
python run_project.py --spec project_spec.yaml --all --resume
```
"""


def _render_research_memo(spec: ProjectSpec) -> str:
    return f"""# Research Memo — {spec.project.title}

## 1. Research question

{spec.research_question}

## 2. Hypothesis

**Economic:** {spec.hypothesis.economic}

**Statistical:** {spec.hypothesis.statistical}

## 3. Data

- Market type: {spec.data.market_type}
- Instrument: {spec.data.instrument or "TBD"}
- Frequency: {spec.data.frequency}
- Sources: {", ".join(spec.data.sources) or "TBD"}
- Timestamp policy: {spec.data.timestamp_policy}

## 4. Target variable

TBD — define precisely once data is loaded (see DATA_DICTIONARY.md).

## 5. Information timing

Every feature must carry an `available_at` timestamp no later than the
decision time it is used for (see ex-ante vs ex-post discussion in
ASSUMPTIONS_AND_RISKS.md). Required fields: {", ".join(spec.data.required_fields) or "TBD"}.

## 6. Baseline

{", ".join(spec.models.baseline) or "TBD"}

## 7. Model set

{", ".join(spec.models.predictive) or "TBD"}

## 8. Validation scheme

Scheme: {spec.validation.scheme} · random k-fold allowed:
{spec.validation.random_kfold_allowed} · leakage audit: {spec.validation.leakage_audit}

## 9. Trading / decision layer

{spec.trading.model_dump()}

## 10. Robustness tests

{chr(10).join(f"- {r}" for r in spec.robustness) or "- TBD"}

## 11. Failure analysis

TBD — populate after the diagnostics stage runs (largest errors,
drawdowns, regime breakdown, parameter stability, ablations).

## 12. Figures / tables

TBD — see reports/figures and reports/tables.

## 13. Results summary

TBD.

## 14. Assumptions / limitations

See ASSUMPTIONS_AND_RISKS.md.

## 15-17. Interview explanations (30s / 2min / 10min)

See INTERVIEW_MASTERY.md.

## 18. Likely interviewer attacks + responses

See INTERVIEW_MASTERY.md.

## 19-20. Resume bullet(s)

See RESUME_BULLETS.md.
"""


def _render_interview_mastery(spec: ProjectSpec) -> str:
    return f"""# Interview Mastery — {spec.project.title}

## 30-second explanation

TBD: what did I study, why did it matter, what did I find/learn?

## 2-minute explanation

TBD: target, data, model ladder, validation, trading layer, biggest
failure insight.

## 10-minute technical walkthrough

TBD: equations, architecture, feature timing, robustness, alternative
explanations, what would change in production.

## Likely interviewer attacks

Generate {spec.outputs.interview_questions_target}+ questions across:
statistics, probability, linear algebra, ML, data cleaning, leakage,
market mechanics, execution, PnL/risk, systems, debugging, and this
project's own limitations. Populate after the research/failure-analysis
stages run so answers can cite real numbers from this project.

## What this project does not prove — cover separately

{chr(10).join(f"- {p}" for p in spec.separate_interview_prep) or "- (none flagged)"}
"""


def _render_resume_bullets(spec: ProjectSpec) -> str:
    return f"""# Resume Bullets — {spec.project.title}

TBD once results are in. Draft skeleton:

> Built a {spec.project.archetype.value.replace('_', ' ')} research pipeline
> for {spec.data.market_type.replace('_', ' ')} data; compared
> {", ".join(spec.models.baseline + spec.models.predictive)} under
> {spec.validation.scheme} validation; [ADD headline finding / PnL / risk
> result once available].
"""


def _render_assumptions(spec: ProjectSpec) -> str:
    return f"""# Assumptions and Risks — {spec.project.title}

## Ex-ante vs ex-post

Every feature in `features/` must declare `available_at` and an
`ex_ante: bool` flag (see FeatureDefinition in the reusable core). Any
feature not demonstrably available at decision time is excluded from the
primary backtest per Gate 2 (quality gates, section 14).

## Known scope limits

{chr(10).join(f"- {c}" for c in spec.project_does_not_cover) or "- TBD"}

## Never claim

- live profitability when only backtested,
- executable fills when using naive touch assumptions,
- causality from correlation,
- production-grade latency realism without evidence,
- market data availability that was not verified.

## Open items

TBD as research proceeds — leakage findings, regime failures, parameter
instability, etc. go here.
"""


def _render_data_dictionary(spec: ProjectSpec) -> str:
    lines = [
        f"# Data Dictionary — {spec.project.title}",
        "",
        "| Field | Source | available_at policy | Notes |",
        "|---|---|---|---|",
    ]
    for field in spec.data.required_fields:
        lines.append(f"| {field} | TBD | {spec.data.timestamp_policy} | TBD |")
    if not spec.data.required_fields:
        lines.append("| TBD | TBD | TBD | TBD |")
    return "\n".join(lines) + "\n"


def _render_requirements() -> str:
    return (
        "# Inherit from the quant_project_factory root pyproject.toml.\n"
        "# Project-specific extras go here.\n"
    )


def _render_run_project(spec: ProjectSpec) -> str:
    return f'''"""Entry point for {spec.project.project_id}.

Delegates to the reusable orchestrator (project_factory.orchestrator)
once the Milestone 2/3 research core is implemented. For now this is a
placeholder that confirms the spec loads correctly.
"""

from pathlib import Path

import typer

from project_factory.schemas import ProjectSpec
import yaml

app = typer.Typer()


@app.command()
def main(spec: Path = typer.Option(Path("project_spec.yaml"))):
    loaded = ProjectSpec.model_validate(yaml.safe_load(spec.read_text()))
    typer.echo(f"Loaded spec for {{loaded.project.project_id}} ({{loaded.project.archetype.value}}).")
    typer.echo("Orchestrator not implemented yet for this archetype — see IMPLEMENTATION_STATUS.md.")


if __name__ == "__main__":
    app()
'''


def initialize_project(spec: ProjectSpec, projects_root: Path | None = None) -> Path:
    root = projects_root or PROJECTS_ROOT
    project_dir = root / spec.project.project_id
    for sub in SUBDIRS:
        (project_dir / sub).mkdir(parents=True, exist_ok=True)
    for sub in ["data/raw", "data/interim", "data/processed"]:
        (project_dir / sub / ".gitkeep").touch(exist_ok=True)

    (project_dir / "project_spec.yaml").write_text(
        yaml.safe_dump(spec.model_dump(mode="json"), sort_keys=False)
    )
    _write_if_absent(project_dir / "README.md", _render_readme(spec))
    _write_if_absent(project_dir / "RESEARCH_MEMO.md", _render_research_memo(spec))
    _write_if_absent(project_dir / "INTERVIEW_MASTERY.md", _render_interview_mastery(spec))
    _write_if_absent(project_dir / "RESUME_BULLETS.md", _render_resume_bullets(spec))
    _write_if_absent(project_dir / "ASSUMPTIONS_AND_RISKS.md", _render_assumptions(spec))
    _write_if_absent(project_dir / "DATA_DICTIONARY.md", _render_data_dictionary(spec))
    _write_if_absent(project_dir / "requirements.txt", _render_requirements())
    _write_if_absent(project_dir / "run_project.py", _render_run_project(spec))

    return project_dir
