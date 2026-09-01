"""CLI entry point (`qpf`) — section 24 / 32.

    qpf analyze-role --jd <path> --call <path> --out <dir>
    qpf show-spec <path/to/project_spec.yaml>
    qpf init-project --spec <path/to/project_spec.yaml>
    qpf run --spec <path> --stage {data,models,trading,robustness} [--all] [--resume]
    qpf report --spec <path>
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
import yaml

import project_factory.archetypes  # noqa: F401  (registers implemented archetypes)
from project_factory.init_project import initialize_project
from project_factory.jd_parser import parse_role
from project_factory.registry import IMPLEMENTED_ARCHETYPES
from project_factory.router import route_archetype
from project_factory.schemas import CandidateConfig, ProjectSpec, RoleInput
from project_factory.spec_builder import build_project_spec

app = typer.Typer(add_completion=False, help="48-hour quant project factory.")

DEFAULT_CANDIDATE_CONFIG = Path(__file__).resolve().parent.parent / "configs" / "candidate.yaml"


def load_candidate_config(path: Path | None = None) -> CandidateConfig:
    path = path or DEFAULT_CANDIDATE_CONFIG
    if not path.exists():
        return CandidateConfig()
    raw = yaml.safe_load(path.read_text()) or {}
    return CandidateConfig.model_validate(raw)


def _infer_firm_and_role(jd_text: str, firm: str | None, role: str | None) -> tuple[str, str]:
    if firm and role:
        return firm, role
    first_line = next((line.strip() for line in jd_text.splitlines() if line.strip()), "")
    for sep in ["—", " - ", " – ", ":"]:
        if sep in first_line:
            left, _, right = first_line.partition(sep)
            left, right = left.strip(), right.strip()
            if left and right:
                return firm or left, role or right
    return firm or "Unknown Firm", role or "Unknown Role"


def _render_role_analysis_md(role_input: RoleInput, analysis, routing) -> str:
    signal_lines = [
        f"- {dim}: {analysis.signals.get(dim)}"
        + (f"  (matched: {analysis.matched_keywords.get(dim)})" if analysis.matched_keywords.get(dim) else "")
        for dim in analysis.signals.model_dump()
    ]
    discrepancy_lines = (
        "\n".join(f"- {d}" for d in analysis.notes_vs_jd_discrepancies)
        or "- None flagged."
    )
    return f"""# Role Analysis — {role_input.firm_name} / {role_input.role_title}

## Extracted signals (0-5)

{chr(10).join(signal_lines)}

## Asset classes mentioned

{", ".join(analysis.asset_classes) or "none detected"}

## Systematic vs discretionary

{analysis.systematic_vs_discretionary}

## Trading / research / execution focus

{", ".join(analysis.trading_vs_research_vs_execution)}

## Data frequency hints

{", ".join(analysis.data_frequency_hints) or "none detected"}

## Languages mentioned

{", ".join(analysis.languages_mentioned) or "none detected"}

## Call-notes claims flagged as anecdotal (section 3.2)

Official JD is the hard anchor; these are opinions/anecdotes from insider
call notes that should not silently override explicit JD requirements:

{discrepancy_lines}

## Routing decision

- **Primary archetype:** {routing.primary_archetype.value}
- **Secondary archetype:** {routing.secondary_archetype.value if routing.secondary_archetype else "none"}
- **Routing confidence:** {routing.routing_confidence:.2f}

### Why the primary archetype matches

{chr(10).join(f"- {r}" for r in routing.why_primary_matches)}

### What the primary project does NOT cover

{chr(10).join(f"- {c}" for c in routing.what_primary_does_not_cover) or "- (none)"}

### Separate interview prep needed to cover the gap

{chr(10).join(f"- {c}" for c in routing.interview_prep_needed_to_cover_gap) or "- (none)"}

### All archetype scores

{chr(10).join(f"- {a}: {v:.2f}" for a, v in sorted(routing.archetype_scores.items(), key=lambda kv: -kv[1]))}
"""


@app.command("analyze-role")
def analyze_role(
    jd: Path = typer.Option(..., exists=True, readable=True, help="Path to job description text file."),
    call: Path | None = typer.Option(None, exists=True, readable=True, help="Path to insider call notes text file."),
    out: Path = typer.Option(..., help="Output directory for ROLE_ANALYSIS.md / project_spec.yaml / routing.json."),
    firm: str | None = typer.Option(None, help="Firm name (inferred from JD first line if omitted)."),
    role: str | None = typer.Option(None, help="Role title (inferred from JD first line if omitted)."),
    location: str | None = typer.Option(None),
    known_interview_details: str | None = typer.Option(None),
    application_deadline: str | None = typer.Option(None),
    candidate_config: Path | None = typer.Option(None, help="Path to candidate.yaml (defaults to configs/candidate.yaml)."),
) -> None:
    """Parse a JD (+ optional call notes), route to an archetype, and
    write ROLE_ANALYSIS.md / project_spec.yaml / routing.json to --out."""
    jd_text = jd.read_text()
    call_text = call.read_text() if call else None
    firm_name, role_title = _infer_firm_and_role(jd_text, firm, role)

    role_input = RoleInput(
        firm_name=firm_name,
        role_title=role_title,
        job_description=jd_text,
        insider_call_notes=call_text,
        location=location,
        known_interview_details=known_interview_details,
        application_deadline=application_deadline,
    )

    analysis = parse_role(role_input)
    routing = route_archetype(analysis)
    candidate = load_candidate_config(candidate_config)
    spec = build_project_spec(analysis, routing, candidate)

    out.mkdir(parents=True, exist_ok=True)
    (out / "routing.json").write_text(
        json.dumps(
            {
                "primary_archetype": routing.primary_archetype.value,
                "secondary_archetype": routing.secondary_archetype.value if routing.secondary_archetype else None,
                "routing_confidence": routing.routing_confidence,
                "why_primary_matches": routing.why_primary_matches,
                "what_primary_does_not_cover": routing.what_primary_does_not_cover,
                "interview_prep_needed_to_cover_gap": routing.interview_prep_needed_to_cover_gap,
                "archetype_scores": routing.archetype_scores,
            },
            indent=2,
        )
    )
    (out / "project_spec.yaml").write_text(yaml.safe_dump(spec.model_dump(mode="json"), sort_keys=False))
    (out / "ROLE_ANALYSIS.md").write_text(_render_role_analysis_md(role_input, analysis, routing))

    implemented = routing.primary_archetype in IMPLEMENTED_ARCHETYPES
    typer.echo(f"primary_archetype: {routing.primary_archetype.value}")
    typer.echo(f"secondary_archetype: {routing.secondary_archetype.value if routing.secondary_archetype else 'none'}")
    typer.echo(f"routing_confidence: {routing.routing_confidence:.2f}")
    typer.echo(f"wrote: {out / 'ROLE_ANALYSIS.md'}, {out / 'project_spec.yaml'}, {out / 'routing.json'}")
    if not implemented:
        typer.echo(
            f"note: '{routing.primary_archetype.value}' has no runnable data "
            f"adapter/strategy yet (see IMPLEMENTATION_STATUS.md); "
            f"'qpf run' will not work for this spec until it does."
        )


@app.command("show-spec")
def show_spec(spec_path: Path = typer.Argument(..., exists=True, readable=True)) -> None:
    """Load and pretty-print a project_spec.yaml, validating it against
    the ProjectSpec schema."""
    spec = ProjectSpec.model_validate(yaml.safe_load(spec_path.read_text()))
    typer.echo(yaml.safe_dump(spec.model_dump(mode="json"), sort_keys=False))


@app.command("init-project")
def init_project_cmd(
    spec: Path = typer.Option(..., exists=True, readable=True, help="Path to project_spec.yaml"),
) -> None:
    """Create the projects/<project_id>/ folder structure from a spec."""
    project_spec = ProjectSpec.model_validate(yaml.safe_load(spec.read_text()))
    project_dir = initialize_project(project_spec)
    typer.echo(f"initialized project at: {project_dir}")


@app.command("run")
def run_cmd(
    spec: Path = typer.Option(..., exists=True, readable=True),
    stage: str | None = typer.Option(None, help="One of: data, models, trading, robustness."),
    all_stages: bool = typer.Option(False, "--all", help="Run every stage in order."),
    resume: bool = typer.Option(False, help="Skip stages already cached from a prior run."),
    synthetic: bool = typer.Option(
        False,
        "--synthetic",
        help=(
            "Use the archetype's synthetic (non-real) data adapter instead of the "
            "registered production one — exercises the full pipeline without live "
            "data access. Never use this to report results as real."
        ),
    ),
) -> None:
    """Run the research orchestrator for a spec. Only archetypes in
    IMPLEMENTED_ARCHETYPES have a working pipeline behind this command;
    see IMPLEMENTATION_STATUS.md for current coverage."""
    project_spec = ProjectSpec.model_validate(yaml.safe_load(spec.read_text()))
    archetype = project_spec.project.archetype
    if archetype not in IMPLEMENTED_ARCHETYPES:
        typer.echo(
            f"'{archetype.value}' has no implemented data adapter / strategy yet. "
            f"See IMPLEMENTATION_STATUS.md for what's built so far."
        )
        raise typer.Exit(code=1)
    from project_factory import registry
    from project_factory.orchestrator import run_stage  # deferred import: only needed once implemented

    if not synthetic and (all_stages or stage == "data"):
        adapter = registry.get_data_adapter(archetype)
        check = getattr(adapter, "check_connectivity", None)
        if callable(check):
            try:
                check()
            except Exception as exc:  # noqa: BLE001 - top-level CLI error boundary
                typer.echo(f"data source connectivity check failed: {exc}")
                raise typer.Exit(code=1) from exc
    elif synthetic:
        typer.echo("--synthetic: using non-real data. Do not report these results as real.")

    try:
        results = run_stage(
            project_spec, stage=stage, all_stages=all_stages, resume=resume, synthetic=synthetic
        )
    except Exception as exc:  # noqa: BLE001 - top-level CLI error boundary
        typer.echo(f"stage {stage or 'all'!r} failed: {exc}")
        raise typer.Exit(code=1) from exc

    for key in results:
        typer.echo(f"completed stage output: {key}")


@app.command("report")
def report_cmd(spec: Path = typer.Option(..., exists=True, readable=True)) -> None:
    """Generate the recruiting pack (figures/tables/memo/interview docs)
    from experiment metadata. Requires 'run' to have completed first."""
    project_spec = ProjectSpec.model_validate(yaml.safe_load(spec.read_text()))
    archetype = project_spec.project.archetype
    if archetype not in IMPLEMENTED_ARCHETYPES:
        typer.echo(
            f"'{archetype.value}' has no implemented reporting pipeline yet. "
            f"See IMPLEMENTATION_STATUS.md."
        )
        raise typer.Exit(code=1)
    from project_factory.reporting.memo import build_reports  # deferred import

    build_reports(project_spec)


if __name__ == "__main__":
    app()
