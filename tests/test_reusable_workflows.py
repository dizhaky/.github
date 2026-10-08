"""Tests verifying reusable workflow runner defaults and documentation."""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

RUNNER_DEFAULT_RE = re.compile(r"^\s+runner:\s*\n\s+type:\s*string\s*\n\s+default:\s*'\"ubuntu-latest\"'", re.M)


def test_reusable_workflow_runner_defaults():
    reusable_files = [
        "reusable-ci.yml",
        "reusable-nightly-maintenance.yml",
        "reusable-scan-failure-alert.yml",
        "reusable-secret-scan.yml",
    ]
    for filename in reusable_files:
        path = WORKFLOWS_DIR / filename
        assert path.exists(), f"Workflow file {filename} missing"
        content = path.read_text()
        assert RUNNER_DEFAULT_RE.search(content), f"runner default in {filename} must be '\"ubuntu-latest\"'"


def test_agent_documentation_records_runner_policy():
    agents_md = (REPO_ROOT / "AGENTS.md").read_text()
    assert "Self-hosted runner policy" in agents_md or "DAN-4030" in agents_md
    assert (REPO_ROOT / "CLAUDE.md").read_text() == "@AGENTS.md\n"
