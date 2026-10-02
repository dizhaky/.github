"""The Dependabot template must remain a read-only metadata reporter."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
TEMPLATE=ROOT/".github/repo-templates/dependabot-auto-merge.yml"

class DependabotReporterTemplateTest(unittest.TestCase):
    def test_reporter_never_checks_out_or_executes_pr_code(self):
        source=TEMPLATE.read_text()
        self.assertNotIn("actions/checkout",source)
        self.assertNotIn("fetch-metadata",source)
        self.assertIn("gh api --paginate --slurp",source)
        self.assertIn("pulls?state=open&per_page=100",source)

    def test_reporter_has_no_mutation_or_enrollment_authority(self):
        source=TEMPLATE.read_text()
        for forbidden in ("gh pr merge","enablePullRequestAutoMerge","mergePullRequest","--method POST","--method PATCH","contents: write","pull-requests: write"):
            self.assertNotIn(forbidden,source)
        self.assertIn("contents: read",source)
        self.assertIn("pull-requests: read",source)
        self.assertIn("GH_TOKEN: ${{ github.token }}",source)

    def test_reporter_scopes_owned_repositories_and_passes_context_via_environment(self):
        source=TEMPLATE.read_text()
        self.assertIn("github.repository_owner == 'dizhaky'",source)
        self.assertIn("DELIVERY_REPOSITORY: ${{ github.repository }}",source)
        self.assertIn('"repos/$DELIVERY_REPOSITORY/pulls?',source)
        self.assertNotIn("secrets.AUTO_MERGE_PAT",source)

if __name__=="__main__":unittest.main()
