"""Exercise the two-stage review capture without network access."""

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
SOURCE = ROOT / ".github/workflows/post-merge-review-payload.yml"
CAPTURE = ROOT / ".github/workflows/post-merge-review-capture.yml"


class PostMergeReviewCaptureTest(unittest.TestCase):
    def test_fork_safe_two_stage_contract(self):
        source = SOURCE.read_text()
        capture = CAPTURE.read_text()
        self.assertIn("pull_request_review:", source)
        self.assertIn("actions/upload-artifact@v4", source)
        self.assertNotIn("issues: write", source)
        self.assertIn("workflow_run:", capture)
        self.assertIn("actions/download-artifact@v4", capture)
        self.assertIn("issues: write", capture)
        self.assertNotIn("continue-on-error", capture)
        self.assertIn(
            "group: post-merge-review-${{ needs.validate.outputs.review_id }}",
            capture,
        )
        self.assertIn("--paginate --slurp", capture)
        self.assertIn("state=all&per_page=100", capture)
        self.assertIn("needs: validate", capture)
        self.assertNotIn("--search", capture)

    def run_capture(
        self,
        *,
        merged=True,
        author="owner",
        reviewer="chatgpt-codex-connector[bot]",
        submitted="2026-09-05T12:01:00Z",
        review_id=1,
        existing="",
        body="hostile ' $(touch marker) review body",
        api_fail=False,
        lookup_fail=False,
        base_ref="release",
        associated_prs=(12,),
        event="pull_request_review",
        workflow_path=".github/workflows/post-merge-review-payload.yml",
        actor_id=100,
        issue_pages=None,
        create_fail=False,
    ):
        validation, capture = CAPTURE.read_text().split("\n  capture:", 1)
        shell = "\n".join(
            textwrap.dedent(stage.split("        run: |\n", 1)[1])
            for stage in (validation, capture)
        )
        self.assertNotIn("${{", shell)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            marker = root / "marker"
            payload = root / "review.json"
            payload.write_text(
                json.dumps({"pr_number": 12, "review_id": review_id})
            )
            pr = {
                "merged": merged,
                "user": {"login": author},
                "title": "A title | with a table break",
                "html_url": "https://github.com/owner/repo/pull/12",
                "merged_at": "2026-09-05T12:00:00Z",
                "base": {"ref": base_ref},
            }
            review = {
                "id": review_id,
                "user": {"login": reviewer, "id": 100},
                "html_url": "https://github.com/owner/repo/pull/12#pullrequestreview-1",
                "state": "COMMENTED",
                "submitted_at": submitted,
                "body": body.replace("marker", str(marker)),
            }
            (root / "event.json").write_text(
                json.dumps(
                    {
                        "workflow_run": {
                            "event": event,
                            "path": workflow_path,
                            "actor": {"id": actor_id},
                            "pull_requests": [
                                {"number": n} for n in associated_prs
                            ],
                        }
                    }
                )
            )
            if issue_pages is None:
                issue_pages = (
                    [
                        [
                            {
                                "number": int(existing),
                                "title": (
                                    f"Post-merge review {review_id} "
                                    f"on #12 by {reviewer}"
                                ),
                                "body": "legacy issue",
                            }
                        ]
                    ]
                    if existing
                    else [[]]
                )
            (root / "issues.json").write_text(json.dumps(issue_pages))
            (root / "pr.json").write_text(json.dumps(pr))
            (root / "review.json.fixture").write_text(json.dumps(review))
            gh = root / "gh"
            gh.write_text(
                f"#!{sys.executable}\n"
                + textwrap.dedent(
                    """
                    import json, os, sys
                    from pathlib import Path
                    root = Path(os.environ["FIXTURE_ROOT"])
                    args = sys.argv[1:]
                    if args[0] == "api":
                        if os.environ.get("API_FAIL") == "1":
                            raise SystemExit(1)
                        if "--paginate" in args:
                            assert "--slurp" in args
                            assert "state=all&per_page=100" in args[-1]
                            if os.environ.get("LOOKUP_FAIL") == "1":
                                raise SystemExit(1)
                            print((root / "issues.json").read_text())
                        elif "/reviews/" in args[1]:
                            print((root / "review.json.fixture").read_text())
                        else:
                            print((root / "pr.json").read_text())
                    elif args[:2] == ["issue", "create"]:
                        if os.environ.get("CREATE_FAIL") == "1":
                            raise SystemExit(1)
                        content = Path(
                            args[args.index("--body-file") + 1]
                        ).read_text()
                        with (root / "mutations.jsonl").open("a") as output:
                            output.write(
                                json.dumps({"args": args, "body": content})
                                + "\\n"
                            )
                    else:
                        raise SystemExit(
                            "unexpected gh invocation: " + repr(args)
                        )
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
                    "PAYLOAD_FILE": str(payload),
                    "GITHUB_EVENT_PATH": str(root / "event.json"),
                    "GITHUB_OUTPUT": str(root / "outputs"),
                    "CREATE_FAIL": str(int(create_fail)),
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
        self.assertIn("including inline comments", mutations[0]["body"])
        self.assertIn("branch release", mutations[0]["body"])

    def test_open_pr_does_not_create_issue(self):
        result, mutations = self.run_capture(merged=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(mutations, [])

    def test_author_reply_uses_an_allowed_reviewer(self):
        bot = "github-actions[bot]"
        result, mutations = self.run_capture(author=bot, reviewer=bot)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(mutations, [])

    def test_outsider_review_does_not_create_issue(self):
        result, mutations = self.run_capture(reviewer="random-contributor")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(mutations, [])

    def test_premerge_review_does_not_create_issue(self):
        result, mutations = self.run_capture(submitted="2026-09-05T11:59:59Z")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(mutations, [])

    def test_same_second_is_captured_without_claiming_order(self):
        result, mutations = self.run_capture(submitted="2026-09-05T12:00:00Z")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("same second", mutations[0]["body"])

    def test_existing_open_or_closed_issue_is_a_noop(self):
        result, mutations = self.run_capture(existing="47")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(mutations, [])
        self.assertIn("already captured", result.stdout)

    def test_each_review_uses_a_distinct_issue_identity(self):
        result, mutations = self.run_capture(review_id=987)
        self.assertEqual(result.returncode, 0, result.stderr)
        args = mutations[0]["args"]
        title = args[args.index("--title") + 1]
        self.assertIn("review 987", title)

    def test_review_body_is_bounded(self):
        result, mutations = self.run_capture(body="x" * 70_000)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLess(len(mutations[0]["body"].encode()), 65_536)

    def test_issue_lookup_failure_does_not_create_duplicate(self):
        result, mutations = self.run_capture(lookup_fail=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(mutations, [])

    def test_missing_or_unrelated_run_pr_fails_visibly(self):
        for prs in ((), (999,)):
            with self.subTest(prs=prs):
                result, mutations = self.run_capture(associated_prs=prs)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(mutations, [])

    def test_wrong_source_event_workflow_or_actor_fails_visibly(self):
        for overrides in (
            {"event": "push"},
            {"workflow_path": ".github/workflows/other.yml"},
            {"actor_id": 999},
        ):
            with self.subTest(overrides=overrides):
                result, mutations = self.run_capture(**overrides)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(mutations, [])

    def test_capture_beyond_first_thousand_issues_is_not_duplicated(self):
        pages = [
            [
                {"number": 2000 + i, "title": "Unrelated", "body": ""}
                for i in range(100)
            ]
            for _ in range(10)
        ]
        pages.append(
            [
                {
                    "number": 47,
                    "title": (
                        "Post-merge review 1 on #12 by "
                        "chatgpt-codex-connector[bot]"
                    ),
                    "body": "legacy",
                }
            ]
        )
        result, mutations = self.run_capture(issue_pages=pages)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(mutations, [])
        self.assertIn("issue #47", result.stdout)

    def test_renamed_issue_is_found_by_body_marker(self):
        result, mutations = self.run_capture(
            issue_pages=[
                [
                    {
                        "number": 47,
                        "title": "Renamed during triage",
                        "body": "<!-- post-merge-review:1 -->\n\nDescription",
                    }
                ]
            ]
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(mutations, [])

    def test_issue_creation_failure_is_visible(self):
        result, mutations = self.run_capture(create_fail=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(mutations, [])

    def test_api_failure_is_non_mutating(self):
        result, mutations = self.run_capture(api_fail=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(mutations, [])


if __name__ == "__main__":
    unittest.main()
