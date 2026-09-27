"""Tests verifying reusable workflow runner defaults and documentation."""

from pathlib import Path
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"


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
        data = yaml.safe_load(path.read_text())
        on_val = data.get("on") or data.get(True, {})
        workflow_call = on_val.get("workflow_call", {})
        inputs = workflow_call.get("inputs", {})
        assert "runner" in inputs, f"runner input missing in {filename}"
        assert inputs["runner"]["default"] == '"ubuntu-latest"', f"runner default in {filename} must be '\"ubuntu-latest\"'"


def test_agent_documentation_records_runner_policy():
    agents_md = (REPO_ROOT / "AGENTS.md").read_text()
    claude_md = (REPO_ROOT / "CLAUDE.md").read_text()
    assert "Self-hosted runner policy" in agents_md or "DAN-4030" in agents_md
    assert "Self-hosted runner policy" in claude_md or "DAN-4030" in claude_md
