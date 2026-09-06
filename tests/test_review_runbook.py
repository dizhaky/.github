"""Regression checks for central review automation guidance and audits."""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ReviewRunbookTest(unittest.TestCase):
    def test_debug_scanner_uses_fetch_metadata_ecosystem_value(self):
        scanner = (ROOT / "scripts/debug_scan.py").read_text()
        self.assertIn("package-ecosystem == 'github_actions'", scanner)
        self.assertNotIn("package-ecosystem == 'github-actions'", scanner)

    def test_review_recipe_grants_comment_permissions_and_reads_base_rules(self):
        runbook = (ROOT / "docs/RUNBOOKS.md").read_text()
        section = runbook.split("### Posting reviews", 1)[1].split("Canonical recipe", 1)[0]
        self.assertIn("pull-requests: write", section)
        self.assertIn("issues: write", section)
        self.assertIn("BASE_SHA", section)
        self.assertIn("AGENTS.md", section)
        self.assertIn("CLAUDE.md", section)
        self.assertIn("12 KiB", section)
        self.assertNotIn("do NOT read CLAUDE.md/AGENTS.md", section)
        self.assertNotIn("Bash(gh api:*)", section)
        self.assertIn("Bash(gh api --method GET repos/$REPO/contents/AGENTS.md?ref=$BASE_SHA)", section)
        self.assertIn("Bash(gh api --method GET repos/$REPO/contents/CLAUDE.md?ref=$BASE_SHA)", section)

    def test_primary_commands_and_ci_use_pytest_isolation(self):
        claude = (ROOT / "CLAUDE.md").read_text()
        workflow = (ROOT / ".github/workflows/template-tests.yml").read_text()
        self.assertIn('| Test | `python3 -m pytest -q tests` |', claude)
        self.assertIn("python -m pytest -q tests", workflow)
        self.assertTrue((ROOT / "tests/conftest.py").is_file())

    def test_new_system_log_entries_have_canonical_metadata(self):
        log = (ROOT / "docs/system-log/2026-09-06.md").read_text()
        entries = [part for part in log.split("\n## ")[1:] if part.strip()]
        self.assertGreaterEqual(len(entries), 2)
        for entry in entries:
            heading = entry.splitlines()[0]
            self.assertRegex(heading, r"^2026-09-06T\d{2}:\d{2}:\d{2}Z")
            self.assertIn("- **Agent/tool:**", entry)

    def test_missing_historical_audits_are_present(self):
        august_8 = (ROOT / "docs/system-log/2026-08-08.md").read_text()
        august_10 = (ROOT / "docs/system-log/2026-08-10.md").read_text()
        self.assertIn("PR #15", august_8)
        self.assertIn("7c7cb7d", august_8)
        self.assertIn("dotfiles#628", august_10)
        self.assertIn("PR #16", august_10)
        self.assertIn("PR #17", august_10)

    def test_agent_references_are_clone_portable(self):
        agents = (ROOT / "AGENTS.md").read_text()
        self.assertNotIn("file:///Users/", agents)
        self.assertIn("https://github.com/dizhaky/", agents)


if __name__ == "__main__":
    unittest.main()
