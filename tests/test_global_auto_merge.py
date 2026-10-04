"""Offline safety boundaries for the account-wide merge reconciler."""
import copy
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("global_auto_merge", ROOT / "scripts/global_auto_merge.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def pr(**overrides):
    value = {
        "id": "PR_1", "number": 1, "state": "OPEN", "isDraft": False,
        "headRefOid": "a" * 40, "baseRefName": "main", "mergeable": "MERGEABLE",
        "mergeStateStatus": "CLEAN", "reviewDecision": "APPROVED",
        "viewerCanEnableAutoMerge": False, "autoMergeRequest": None,
        "baseRef": {"branchProtectionRule": {
            "requiresStatusChecks": True, "requiredStatusCheckContexts": ["test"],
        }},
    }
    value.update(overrides)
    return value


GREEN = [{"name": "test", "status": "completed", "conclusion": "success", "app": {"id": 1}}]


@pytest.mark.parametrize("overrides,reason", [
    ({"isDraft": True}, "draft"),
    ({"state": "CLOSED"}, "not_open"),
    ({"mergeable": "CONFLICTING"}, "not_mergeable"),
    ({"mergeable": "UNKNOWN"}, "not_mergeable"),
    ({"reviewDecision": "CHANGES_REQUESTED"}, "changes_requested"),
    ({"mergeStateStatus": "BEHIND"}, "merge_state"),
])
def test_pr_holds(overrides, reason):
    assert module.blocker(pr(**overrides), [], GREEN, [], []) == reason


def test_do_not_merge_is_author_independent():
    assert module.blocker(pr(), ["do-not-merge"], GREEN, [], []) == "label_hold"


def test_unprotected_branch_is_not_directly_merged():
    assert module.blocker(pr(baseRef={"branchProtectionRule": None}), [], GREEN, [], []) == "no_required_checks"


def test_ruleset_required_checks_are_supported():
    rules = [{"type": "required_status_checks", "parameters": {
        "required_status_checks": [{"context": "test", "integration_id": 1}],
    }}]
    assert module.blocker(pr(baseRef={"branchProtectionRule": None}), [], GREEN, [], rules) is None


@pytest.mark.parametrize("checks,statuses,reason", [
    ([], [], "missing_required_checks"),
    ([{"name": "test", "status": "queued", "conclusion": None}], [], "checks_not_green"),
    ([{"name": "test", "status": "completed", "conclusion": "failure"}], [], "checks_not_green"),
    (GREEN, [{"context": "external", "state": "pending"}], "statuses_not_green"),
])
def test_checks_fail_closed(checks, statuses, reason):
    assert module.blocker(pr(), [], checks, statuses, []) == reason


def test_historical_status_failure_does_not_override_latest_success():
    statuses = [{"context": "ci", "state": "success"}, {"context": "ci", "state": "failure"}]
    assert module.blocker(pr(), [], GREEN, statuses, []) is None


def test_pending_reviews_can_enroll_natively_after_ci_passes():
    assert module.blocker(pr(mergeStateStatus="BLOCKED", reviewDecision="REVIEW_REQUIRED", viewerCanEnableAutoMerge=True), [], GREEN, [], []) is None


class FakeAPI:
    def __init__(self):
        self.actions = []
        self.snapshots = [pr(), pr()]
        self.checks = [copy.deepcopy(GREEN), copy.deepcopy(GREEN)]
        self.labels = []
        self.head_repo = {"full_name": "dizhaky/example"}
        self.author_association = "OWNER"
        self.repos = [{"full_name": "dizhaky/example", "archived": False,
                       "disabled": False, "permissions": {"admin": True}}]
        self.repo = {**self.repos[0], "allow_auto_merge": False, "allow_squash_merge": True}

    def rest(self, path, *, paginate=False, method="GET", body=None):
        if method != "GET":
            self.actions.append((method, path, body))
            return {**self.repo, **body}
        if path == "user":
            return {"login": "dizhaky"}
        if path == "repos/dizhaky/.github/commits/main":
            return {"sha": "c" * 40}
        if path.startswith("user/repos?"):
            assert paginate
            return copy.deepcopy(self.repos)
        if path.endswith("pulls?state=open&per_page=100"):
            assert paginate
            return [{"number": 1}]
        if "/check-runs?" in path:
            assert paginate
            return [{"check_runs": self.checks.pop(0)}]
        if path.endswith("statuses?per_page=100"):
            assert paginate
            digest = module.hashlib.sha256(json.dumps({"reviews":[],"comments":[],"threads":[]},sort_keys=True).encode()).hexdigest()
            return [{"context": module.AI_CONTEXT, "state": "success", "created_at":"2026-10-02T23:00:00Z", "creator": {"login": "dizhaky"}, "target_url": "https://github.com/dizhaky/.github/commit/" + "c" * 40, "description": "AI verified receipt:" + digest + " worker:" + "c" * 40}]
        if path.endswith("/reviews?per_page=100") or path.endswith("/comments?per_page=100"):
            return []
        if "/rules/branches/" in path:
            assert paginate
            return []
        if path.endswith("/pulls/1"):
            return {"head": {"sha": "a" * 40, "repo": self.head_repo},
                    "author_association": self.author_association, "labels": [{"name": name} for name in self.labels]}
        return copy.deepcopy(self.repo)

    def pull_request(self, repo, number):
        return self.snapshots.pop(0)

    def threads(self,repo,number):
        return []

    def merge(self, repo, number, method, head, disable=False):
        self.actions.append(("disable" if disable else "merge", repo, number, method, head))


def test_reporter_never_mutates_settings_or_enrollment_even_with_apply():
    api = FakeAPI()
    result = module.reconcile(api, apply=True)
    assert result["errors"] == 0
    assert api.actions == []
    assert result["writerMode"]=="reporter" and result["pull_requests"][0]["outcome"]=="eligible_for_ai_controller"


def test_dry_run_does_not_mutate():
    api = FakeAPI()
    module.reconcile(api, apply=False)
    assert api.actions == []


@pytest.mark.parametrize("field,value", [("archived", True), ("disabled", True), ("permissions", None), ("permissions", {"admin": False})])
def test_skips_ineligible_repositories(field, value):
    api = FakeAPI()
    api.repos[0][field] = value
    module.reconcile(api, apply=True)
    assert api.actions == []


def test_head_race_does_not_merge():
    api = FakeAPI()
    api.snapshots[1]["headRefOid"] = "b" * 40
    module.reconcile(api, apply=True)
    assert not any(a[0] == "merge" for a in api.actions)


def test_late_failed_check_does_not_merge():
    api = FakeAPI()
    api.checks[1].append({"name": "scan", "status": "completed", "conclusion": "failure"})
    module.reconcile(api, apply=True)
    assert not any(a[0] == "merge" for a in api.actions)


def test_label_hold_reports_existing_native_request_to_single_writer():
    api = FakeAPI()
    api.labels = ["do-not-merge"]
    api.snapshots[0]["autoMergeRequest"] = {"enabledAt": "now"}
    module.reconcile(api, apply=True)
    assert api.actions==[]
    assert not any(a[0] == "merge" for a in api.actions)


def test_api_failure_is_visible_not_clean():
    api = FakeAPI()
    api.pull_request = lambda *args: (_ for _ in ()).throw(module.APIError("unavailable"))
    result = module.reconcile(api, apply=True)
    assert result["errors"] == 1
    assert not any(a[0] == "merge" for a in api.actions)


def test_paginated_check_envelopes_are_all_flattened():
    api = FakeAPI()
    original = api.rest
    def request(path, **kwargs):
        if "/check-runs?" in path:
            return [{"check_runs": GREEN}, {"check_runs": [{"name": "late", "status": "queued", "conclusion": None}]}]
        return original(path, **kwargs)
    api.rest = request
    module.reconcile(api, apply=True)
    assert not any(a[0] == "merge" for a in api.actions)


def test_workflow_trust_boundary():
    source = (ROOT / ".github/workflows/global-auto-merge.yml").read_text()
    assert "github.ref == format('refs/heads/{0}', github.event.repository.default_branch)" in source
    assert "ref: ${{ github.event.repository.default_branch }}" in source
    assert "persist-credentials: false" in source
    assert "pull_request:" not in source
    assert "secrets.AUTO_MERGE_PAT || secrets.GH_PAT" in source
    assert "--admin" not in source


def test_rest_pagination_flattens_arrays_but_preserves_check_envelopes():
    api = module.GitHub()
    with patch.object(api, "run", return_value=json.dumps([[{"number": 1}], [{"number": 101}]])) as run:
        assert api.rest("pulls", paginate=True) == [{"number": 1}, {"number": 101}]
        assert "--paginate" in run.call_args.args[0]
        assert "--slurp" in run.call_args.args[0]
    pages = [{"check_runs": GREEN}, {"check_runs": []}]
    with patch.object(api, "run", return_value=json.dumps(pages)):
        assert api.rest("checks", paginate=True) == pages


def test_native_merge_command_never_uses_admin_or_deletes_branches():
    api = module.GitHub()
    with patch.object(api, "run", return_value="") as run:
        api.merge("org/repo", 23, "squash", "a" * 40)
        assert run.call_args.args[0] == [
            "pr", "merge", "23", "--repo", "org/repo", "--auto", "--squash",
            "--match-head-commit", "a" * 40,
        ]


def test_rest_errors_do_not_become_empty_prs():
    api = module.GitHub()
    with patch.object(api, "run", side_effect=module.APIError("unavailable")):
        with pytest.raises(module.APIError):
            api.pull_request("org/repo", 1)


def test_pull_request_normalizes_rest_payload():
    api = module.GitHub()
    rest_pr = {
        "id": 99, "number": 1, "state": "open", "draft": False,
        "mergeable": True, "mergeable_state": "clean", "auto_merge": None,
        "head": {"sha": "a" * 40}, "base": {"ref": "main"},
    }
    reviews = [
        {"user": {"login": "alice"}, "state": "APPROVED"},
        {"user": {"login": "bob"}, "state": "CHANGES_REQUESTED"},
    ]
    protection = {"required_status_checks": {"contexts": ["test"]}}

    def fake_rest(path, **kwargs):
        if path.endswith("/pulls/1"):
            return rest_pr
        if "/reviews" in path:
            return reviews
        if "/protection" in path:
            return protection
        raise AssertionError(path)

    with patch.object(api, "rest", side_effect=fake_rest):
        pr = api.pull_request("org/repo", 1)
    assert pr["reviewDecision"] == "CHANGES_REQUESTED"
    assert pr["mergeable"] == "MERGEABLE"
    assert pr["mergeStateStatus"] == "CLEAN"
    assert pr["headRefOid"] == "a" * 40
    assert pr["baseRef"]["branchProtectionRule"]["requiredStatusCheckContexts"] == ["test"]


def test_reconcile_aborts_when_graphql_budget_is_low():
    api = FakeAPI()
    api.rate_limit_remaining = lambda: (5000, 50)
    result = module.reconcile(api, apply=True)
    assert result["errors"] == 1
    assert result["error"] == "graphql_rate_limit_low"
    assert api.actions == []


def test_admin_permission_loss_is_rechecked_before_mutation():
    api = FakeAPI()
    api.repo["permissions"] = None
    module.reconcile(api, apply=True)
    assert api.actions == []


def test_label_added_during_checks_prevents_merge():
    api = FakeAPI()
    with patch.object(module, "evidence", side_effect=[(pr(), None), (pr(), "label_hold")]):
        module.reconcile(api, apply=True)
    assert not any(action[0] == "merge" for action in api.actions)


@pytest.mark.parametrize("auto_merge,delete_branch", [(True, False), (False, True), (False, False), (True, True)])
def test_reports_drifted_settings_without_writing(auto_merge, delete_branch):
    api = FakeAPI()
    api.repo.update(allow_auto_merge=auto_merge, delete_branch_on_merge=delete_branch)
    result = module.reconcile(api, apply=True)
    expected = {field: True for field, enabled in (
        ("allow_auto_merge", auto_merge), ("delete_branch_on_merge", delete_branch),
    ) if not enabled}
    assert api.actions==[]
    assert result["repositories"][0]["setting"]==("would_enable" if expected else "already_enabled")
    assert result["errors"] == 0


def test_reporter_cannot_attempt_delete_branch_setting_write():
    api = FakeAPI()
    api.repo.update(allow_auto_merge=True, delete_branch_on_merge=False)
    rest = api.rest

    def refuse_setting(path, **kwargs):
        response = rest(path, **kwargs)
        if kwargs.get("method") == "PATCH":
            response["delete_branch_on_merge"] = False
        return response

    api.rest = refuse_setting
    result = module.reconcile(api, apply=True)
    assert result["errors"] == 0 and api.actions==[]
    assert not any(action[0] == "merge" for action in api.actions)


@pytest.mark.parametrize("association", ["NONE", "FIRST_TIMER", "FIRST_TIME_CONTRIBUTOR", "CONTRIBUTOR", None])
def test_external_fork_cannot_self_certify_ci(association):
    api = FakeAPI()
    api.head_repo = {"full_name": "outsider/example"}
    api.author_association = association
    result = module.reconcile(api, apply=True)
    assert result["pull_requests"][0]["reason"] == "untrusted_fork"
    assert not any(action[0] == "merge" for action in api.actions)


@pytest.mark.parametrize("association", ["OWNER", "MEMBER", "COLLABORATOR"])
def test_trusted_maintainer_fork_is_reported_without_enrollment(association):
    api = FakeAPI()
    api.head_repo = {"full_name": "maintainer/example"}
    api.author_association = association
    result = module.reconcile(api, apply=True)
    assert result["errors"] == 0
    assert api.actions==[] and result["pull_requests"][0]["outcome"]=="eligible_for_ai_controller"


@pytest.mark.parametrize("head_repo", [None, {}, {"full_name": ""}])
def test_deleted_or_unknown_head_repo_is_not_trusted(head_repo):
    api = FakeAPI()
    api.head_repo = head_repo
    result = module.reconcile(api, apply=True)
    assert result["pull_requests"][0]["reason"] == "untrusted_fork"
    assert not any(action[0] == "merge" for action in api.actions)


def test_same_repo_branch_does_not_need_author_association():
    api = FakeAPI()
    api.author_association = "NONE"
    module.reconcile(api, apply=True)
    assert api.actions==[]


def test_untrusted_fork_existing_enrollment_is_reported_to_single_writer():
    api = FakeAPI()
    api.head_repo = {"full_name": "outsider/example"}
    api.author_association = "NONE"
    api.snapshots[0]["autoMergeRequest"] = {"enabledAt": "2026-09-07T00:00:00Z"}
    result = module.reconcile(api, apply=True)
    assert result["pull_requests"][0]["outcome"] == "held_for_ai_controller"
    assert api.actions==[]
    assert not any(action[0] == "merge" for action in api.actions)
