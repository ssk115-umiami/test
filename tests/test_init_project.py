from pathlib import Path

from project_factory.init_project import initialize_project
from project_factory.jd_parser import parse_role
from project_factory.router import route_archetype
from project_factory.schemas import CandidateConfig, RoleInput
from project_factory.spec_builder import build_project_spec

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def test_initialize_project_creates_expected_layout(tmp_path):
    role_input = RoleInput(
        firm_name="Headlands Technologies",
        role_title="Quantitative Researcher",
        job_description=(EXAMPLES / "headlands_jd.txt").read_text(),
        insider_call_notes=(EXAMPLES / "headlands_call.txt").read_text(),
    )
    analysis = parse_role(role_input)
    routing = route_archetype(analysis)
    spec = build_project_spec(analysis, routing, CandidateConfig())

    project_dir = initialize_project(spec, projects_root=tmp_path)

    expected_files = [
        "project_spec.yaml",
        "README.md",
        "RESEARCH_MEMO.md",
        "INTERVIEW_MASTERY.md",
        "RESUME_BULLETS.md",
        "ASSUMPTIONS_AND_RISKS.md",
        "DATA_DICTIONARY.md",
        "requirements.txt",
        "run_project.py",
    ]
    for name in expected_files:
        assert (project_dir / name).exists(), f"missing {name}"

    expected_dirs = [
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
    for d in expected_dirs:
        assert (project_dir / d).is_dir(), f"missing dir {d}"

    readme = (project_dir / "README.md").read_text()
    assert spec.project.title in readme
