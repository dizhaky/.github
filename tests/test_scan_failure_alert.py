"""Regressions for default-branch scan alerting."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ALERT = ROOT / ".github/workflows/reusable-scan-failure-alert.yml"
TEMPLATE = ROOT / ".github/repo-templates/secret-scan-alert.yml"


def _step_shell(source: str, step_name: str) -> str:
    marker = f"- name: {step_name}"
    lines = source.splitlines()
    start = next(
        index for index, line in enumerate(lines) if line.strip() == marker
    )
    end = next(
        (
            index
            for index, line in enumerate(lines[start + 1 :], start + 1)
            if line.startswith("      - name: ")
        ),
        len(lines),
    )
    block = "\n".join(lines[start:end])
    return textwrap.dedent(block.split("        run: |\n", 1)[1])


class ScanFailureAlertTest(unittest.TestCase):
    def test_caller_restricts_alerts_to_base_repo_pushes(self):
        text = TEMPLATE.read_text()
        self.assertIn("github.event.workflow_run.event == 'push'", text)
        self.assertIn(
            "github.event.workflow_run.head_repository.full_name == github.repository",
            text,
        )
        self.assertIn(
            "github.event.workflow_run.head_branch == github.event.repository.default_branch",
            text,
        )
        self.assertIn("github.event_name == 'workflow_dispatch'", text)

    def test_mutation_steps_require_current_run(self):
        text = ALERT.read_text()
        self.assertIn("Reject stale runs", text)
        self.assertIn("steps.fresh.outputs.current == 'true'", text)
        self.assertIn(
            "if: inputs.conclusion == 'success' && steps.existing.outputs.number != '' && steps.fresh.outputs.current == 'true'",
            text,
        )

    def test_job_concurrency_serializes_by_workflow_and_branch(self):
        text = ALERT.read_text()
        self.assertIn("concurrency:", text)
        self.assertIn("group: scan-alert-${{ inputs.workflow-name }}-${{ inputs.branch }}", text)
        self.assertIn("cancel-in-progress: false", text)

    def test_freshness_queries_push_events_and_run_identity(self):
        text = ALERT.read_text()
        self.assertIn("--event push", text)
        self.assertIn("databaseId,createdAt,status,conclusion,number,attempt", text)

    def test_alert_body_is_bounded(self):
        text = ALERT.read_text()
        self.assertIn("cut -b 1-60000 > alert-body.md", text)

    def run_fresh(self, *, this_id=11, created="2026-09-07T01:00:00Z", runs, api_fail=False):
        shell = _step_shell(ALERT.read_text(), "Reject stale runs")
        self.assertNotIn("${{", shell)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "this.json").write_text(
                json.dumps(
                    {
                        "id": this_id,
                        "created_at": created,
                        "name": "Secret Scan",
                    }
                )
            )
            (root / "runs.json").write_text(json.dumps(runs))
            gh = root / "gh"
            gh.write_text(
                f"#!{sys.executable}\n"
                + textwrap.dedent(
                    """
                    import os, sys
                    from pathlib import Path
                    root = Path(os.environ["FIXTURE_ROOT"])
                    args = sys.argv[1:]
                    if os.environ.get("API_FAIL") == "1":
                        raise SystemExit(1)
                    if args[0] == "api":
                        print((root / "this.json").read_text())
                    elif args[:2] == ["run", "list"]:
                        print((root / "runs.json").read_text())
                    else:
                        raise SystemExit("unexpected gh invocation: " + repr(args))
                    """
                )
            )
            gh.chmod(0o755)
            result = subprocess.run(
                ["bash", "-e", "-o", "pipefail", "-c", shell],
                cwd=root,
                env={
                    "PATH": str(root) + os.pathsep + os.environ["PATH"],
                    "FIXTURE_ROOT": str(root),
                    "REPO": "owner/repo",
                    "RUN_ID": str(this_id),
                    "WORKFLOW": "Secret Scan",
                    "BRANCH": "main",
                    "GITHUB_OUTPUT": str(root / "outputs"),
                    "API_FAIL": str(int(api_fail)),
                },
                capture_output=True,
                text=True,
                timeout=10,
            )
            outputs = {}
            path = root / "outputs"
            if path.exists():
                for line in path.read_text().splitlines():
                    key, _, value = line.partition("=")
                    outputs[key] = value
            return result, outputs

    def test_newest_success_is_current(self):
        result, outputs = self.run_fresh(
            runs=[
                {"databaseId": 11, "createdAt": "2026-09-07T01:00:00Z"},
                {"databaseId": 10, "createdAt": "2026-09-07T00:00:00Z"},
            ]
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(outputs.get("current"), "true")

    def test_older_success_is_rejected(self):
        result, outputs = self.run_fresh(
            runs=[
                {"databaseId": 12, "createdAt": "2026-09-07T02:00:00Z"},
                {"databaseId": 11, "createdAt": "2026-09-07T01:00:00Z"},
            ]
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(outputs.get("current"), "false")
        self.assertIn("Skipping", result.stdout)

    def test_rehearsal_run_not_in_scan_list_is_current(self):
        result, outputs = self.run_fresh(
            this_id=99,
            runs=[{"databaseId": 11, "createdAt": "2026-09-07T01:00:00Z"}],
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(outputs.get("current"), "true")
        self.assertIn("rehearsal", result.stdout)

    def test_in_progress_newer_run_does_not_suppress_failure(self):
        result, outputs = self.run_fresh(
            runs=[
                {"databaseId": 12, "createdAt": "2026-09-07T02:00:00Z", "status": "in_progress", "conclusion": None},
                {"databaseId": 11, "createdAt": "2026-09-07T01:00:00Z", "status": "completed", "conclusion": "failure"},
            ]
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(outputs.get("current"), "true")

    def test_same_timestamp_higher_database_id_is_rejected(self):
        result, outputs = self.run_fresh(
            runs=[
                {"databaseId": 12, "createdAt": "2026-09-07T01:00:00Z", "status": "completed", "conclusion": "success"},
                {"databaseId": 11, "createdAt": "2026-09-07T01:00:00Z", "status": "completed", "conclusion": "failure"},
            ]
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(outputs.get("current"), "false")
        self.assertIn("Skipping", result.stdout)

    def test_higher_attempt_of_same_run_is_rejected(self):
        result, outputs = self.run_fresh(
            runs=[
                {"databaseId": 11, "createdAt": "2026-09-07T01:00:00Z", "status": "completed", "conclusion": "success", "attempt": 2},
            ]
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(outputs.get("current"), "false")
        self.assertIn("Skipping", result.stdout)


if __name__ == "__main__":
    unittest.main()
