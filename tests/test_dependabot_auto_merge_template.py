"""Regression tests for the Dependabot auto-merge workflow template."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = REPO_ROOT / ".github" / "repo-templates" / "dependabot-auto-merge.yml"


def _template_text() -> str:
    return TEMPLATE.read_text()


def _step_block(step_name: str) -> str:
    lines = _template_text().splitlines()
    marker = f"- name: {step_name}"
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
    return "\n".join(lines[start:end])


def _field_value(block: str, field_name: str) -> str:
    match = re.search(rf"^\s+{re.escape(field_name)}:\s*(.+)$", block, re.M)
    if match is None:
        raise AssertionError(f"Missing {field_name!r} field in block:\n{block}")
    return match.group(1).strip()


def _evaluate_guard(expression: str, *, ecosystem: str, update_type: str) -> bool:
    python_expression = (
        expression.replace("steps.meta.outputs.package-ecosystem", "ecosystem")
        .replace("steps.meta.outputs.update-type", "update_type")
        .replace("&&", "and")
        .replace("||", "or")
    )
    return bool(
        eval(
            python_expression,
            {"__builtins__": {}},
            {"ecosystem": ecosystem, "update_type": update_type},
        )
    )


class DependabotAutoMergeTemplateTest(unittest.TestCase):
    def test_merge_step_targets_repository_without_checkout(self) -> None:
        block = _step_block("Auto-merge github-actions bumps")

        self.assertIn(
            'gh pr merge --auto --squash -R "${{ github.repository }}" '
            '"${{ github.event.pull_request.number }}"',
            block,
        )
        self.assertNotIn("actions/checkout", _template_text())

    def test_ecosystem_guard_uses_fetch_metadata_output_value(self) -> None:
        condition = _field_value(
            _step_block("Auto-merge github-actions bumps"), "if"
        )

        self.assertIn("steps.meta.outputs.package-ecosystem == 'github_actions'", condition)
        self.assertNotIn("github-actions", condition)

    def test_merge_and_skip_guards_are_exact_complements(self) -> None:
        merge_condition = _field_value(
            _step_block("Auto-merge github-actions bumps"), "if"
        )
        skip_condition = _field_value(_step_block("Report skipped auto-merge"), "if")
        ecosystems = [
            "github_actions",
            "github-actions",
            "npm_and_yarn",
            "docker",
            "pip",
            "",
        ]
        update_types = [
            "version-update:semver-patch",
            "version-update:semver-minor",
            "version-update:semver-major",
            "",
        ]

        for ecosystem in ecosystems:
            for update_type in update_types:
                with self.subTest(ecosystem=ecosystem, update_type=update_type):
                    should_merge = ecosystem == "github_actions" and update_type in {
                        "version-update:semver-patch",
                        "version-update:semver-minor",
                    }
                    merge_matches = _evaluate_guard(
                        merge_condition,
                        ecosystem=ecosystem,
                        update_type=update_type,
                    )
                    skip_matches = _evaluate_guard(
                        skip_condition,
                        ecosystem=ecosystem,
                        update_type=update_type,
                    )

                    self.assertEqual(should_merge, merge_matches)
                    self.assertEqual(not should_merge, skip_matches)


if __name__ == "__main__":
    unittest.main()
