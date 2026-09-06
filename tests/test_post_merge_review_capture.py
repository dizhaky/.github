"""Exercise the GitHub-native capture shell without network access."""

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
WORKFLOW = ROOT / ".github/workflows/post-merge-review-capture.yml"


class PostMergeReviewCaptureTest(unittest.TestCase):
    def test_each_review_has_a_unique_concurrency_group(self):
        source = WORKFLOW.read_text()
        self.assertIn(
            "group: post-merge-review-${{ github.event.review.id }}",
            source,
        )
        self.assertNotIn("--search", source)
        self.assertIn("--limit 1000", source)

    def run_capture(
        self,
        *,
        merged=True,
        author="owner",
        reviewer="chatgpt-codex-connector[bot]",
        submitted="2026-09-05T12:01:00Z",
        review_id="1",
        existing="",
        api_fail=False,
        lookup_fail=False,
    ):
        source = WORKFLOW.read_text()
        shell = textwrap.dedent(source.split("        run: |\n", 1)[1])
        self.assertNotIn("${{", shell)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            marker = root / "executed"
            body = f"hostile ' $(touch {marker}) `false`\nreview body"
            fixture = {
                "merged": merged,
                "user": {"login": author},
                "title": body,
                "html_url": "https://github.com/owner/repo/pull/12",
                "merged_at": "2026-09-05T12:00:00Z",
            }
            (root / "fixture.json").write_text(json.dumps(fixture))
            gh = root / "gh"
            gh.write_text(
                f"#!{sys.executable}\n"
                + textwrap.dedent("""
                import json, os, sys
                from pathlib import Path
                root = Path(os.environ['FIXTURE_ROOT'])
                args = sys.argv[1:]
                if args[0] == 'api':
                    if os.environ.get('API_FAIL') == '1': sys.exit(1)
                    print((root / 'fixture.json').read_text())
                elif args[:2] == ['issue', 'list']:
                    if os.environ.get('LOOKUP_FAIL') == '1': sys.exit(1)
                    print(os.environ.get('EXISTING', ''))
                elif args[:2] in (['issue', 'create'], ['issue', 'comment']):
                    content = Path(args[args.index('--body-file') + 1]).read_text()
                    with (root / 'mutations.jsonl').open('a') as output:
                        output.write(json.dumps({'args': args, 'body': content}) + '\\n')
                else:
                    raise SystemExit('unexpected gh invocation: ' + repr(args))
            """)
            )
            gh.chmod(0o755)
            result = subprocess.run(
                ["bash", "-e", "-o", "pipefail", "-c", shell],
                env={
                    "PATH": str(root) + os.pathsep + os.environ["PATH"],
                    "FIXTURE_ROOT": str(root),
                    "REPO": "owner/repo",
                    "PR_NUMBER": "12",
                    "REVIEWER": reviewer,
                    "REVIEW_URL": "https://github.com/owner/repo/pull/12#pullrequestreview-1",
                    "REVIEW_STATE": "commented",
                    "REVIEW_BODY": body,
                    "REVIEW_SUBMITTED_AT": submitted,
                    "REVIEW_ID": review_id,
                    "EXISTING": existing,
                    "API_FAIL": str(int(api_fail)),
                    "LOOKUP_FAIL": str(int(lookup_fail)),
                    "TMPDIR": str(root),
                },
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertFalse(marker.exists(), result.stdout)
            path = root / "mutations.jsonl"
            mutations = (
                [json.loads(line) for line in path.read_text().splitlines()]
                if path.exists()
                else []
            )
            return result, mutations

    def test_late_review_creates_issue_without_executing_body(self):
        result, mutations = self.run_capture()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(mutations), 1)
        self.assertEqual(mutations[0]["args"][:2], ["issue", "create"])
        self.assertIn("hostile", mutations[0]["body"])
        self.assertIn("including inline comments", mutations[0]["body"])

    def test_open_pr_does_not_create_issue(self):
        result, mutations = self.run_capture(merged=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(mutations, [])

    def test_author_reply_does_not_create_issue(self):
        result, mutations = self.run_capture(reviewer="owner")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(mutations, [])

    def test_premerge_review_does_not_create_issue(self):
        result, mutations = self.run_capture(submitted="2026-09-05T11:59:59Z")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(mutations, [])

    def test_missing_timestamp_does_not_create_issue(self):
        result, mutations = self.run_capture(submitted="")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(mutations, [])

    def test_same_second_is_captured_without_claiming_order(self):
        result, mutations = self.run_capture(submitted="2026-09-05T12:00:00Z")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("same second", mutations[0]["body"])

    def test_existing_issue_gets_comment(self):
        result, mutations = self.run_capture(existing="47")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(mutations[0]["args"][:3], ["issue", "comment", "47"])

    def test_each_review_uses_a_distinct_issue_identity(self):
        result, mutations = self.run_capture(review_id="987")
        self.assertEqual(result.returncode, 0, result.stderr)
        args = mutations[0]["args"]
        title = args[args.index("--title") + 1]
        self.assertIn("review 987", title)

    def test_issue_lookup_failure_does_not_create_duplicate(self):
        result, mutations = self.run_capture(lookup_fail=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(mutations, [])

    def test_api_failure_does_not_create_issue(self):
        result, mutations = self.run_capture(api_fail=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(mutations, [])


if __name__ == "__main__":
    unittest.main()
