"""Reconcile native auto-merge across active repositories the token administers.

Only trusted scheduled/default-branch code runs. PR code is never downloaded.
Dry-run is the default; --apply repairs settings and uses normal native merging.
"""
import argparse
import json
import os
import subprocess
from urllib.parse import quote


class APIError(RuntimeError):
    """A failed API call is an error, never an empty successful scan."""


_MERGEABLE_STATE = {
    "clean": "CLEAN",
    "blocked": "BLOCKED",
    "behind": "BEHIND",
    "dirty": "DIRTY",
    "unstable": "UNSTABLE",
    "has_hooks": "UNSTABLE",
    "unknown": "UNKNOWN",
}


class GitHub:
    def run(self, args, body=None):
        result = subprocess.run(
            ["gh", *args], input=json.dumps(body) if body is not None else None,
            text=True, capture_output=True, timeout=180,
        )
        if result.returncode:
            # gh stderr can include request data; do not copy it into public logs.
            raise APIError(f"gh {args[0]} failed (exit {result.returncode})")
        return result.stdout

    def rest(self, path, *, paginate=False, method="GET", body=None):
        args = ["api", "--method", method, "-H", "Cache-Control: no-cache", path]
        if paginate:
            args += ["--paginate", "--slurp"]
        if body is not None:
            args += ["--input", "-"]
        result = json.loads(self.run(args, body))
        if paginate and all(isinstance(page, list) for page in result):
            return [item for page in result for item in page]
        return result

    def rest_optional(self, path, **kwargs):
        try:
            return self.rest(path, **kwargs)
        except APIError:
            return None

    def rate_limit_remaining(self):
        data = self.rest_optional("rate_limit") or {}
        resources = data.get("resources") or {}
        core = int((resources.get("core") or {}).get("remaining") or 0)
        graphql = int((resources.get("graphql") or {}).get("remaining") or 0)
        return core, graphql

    @staticmethod
    def _review_decision(reviews):
        latest = {}
        for review in reviews:
            user = (review.get("user") or {}).get("login")
            state = review.get("state")
            if not user or state in (None, "COMMENTED", "PENDING"):
                continue
            latest[user] = state
        states = set(latest.values())
        if "CHANGES_REQUESTED" in states:
            return "CHANGES_REQUESTED"
        if "APPROVED" in states:
            return "APPROVED"
        return None

    def pull_request(self, repo, number):
        """Return the GraphQL-shaped PR dict callers expect, via REST (DAN-3334).

        Native enrollment (`gh pr merge --auto`) still needs GraphQL — GitHub
        has no REST equivalent — but the per-PR GraphQL *lookup* is gone.
        """
        rest_pr = self.rest(f"repos/{repo}/pulls/{number}")
        reviews = self.rest(
            f"repos/{repo}/pulls/{number}/reviews?per_page=100", paginate=True,
        )
        base_ref = rest_pr["base"]["ref"]
        protection = self.rest_optional(
            f"repos/{repo}/branches/{quote(base_ref, safe='')}/protection",
        )
        status_checks = (protection or {}).get("required_status_checks") or {}
        auto_merge = rest_pr.get("auto_merge")
        mergeable = rest_pr.get("mergeable")
        if mergeable is True:
            mergeable_enum = "MERGEABLE"
        elif mergeable is False:
            mergeable_enum = "CONFLICTING"
        else:
            mergeable_enum = "UNKNOWN"
        return {
            "id": str(rest_pr["id"]),
            "number": rest_pr["number"],
            "state": (rest_pr.get("state") or "").upper(),
            "isDraft": bool(rest_pr.get("draft")),
            "headRefOid": rest_pr["head"]["sha"],
            "baseRefName": base_ref,
            "mergeable": mergeable_enum,
            "mergeStateStatus": _MERGEABLE_STATE.get(
                (rest_pr.get("mergeable_state") or "unknown").lower(), "UNKNOWN",
            ),
            "reviewDecision": self._review_decision(reviews),
            "viewerCanEnableAutoMerge": (
                not rest_pr.get("draft") and rest_pr.get("state") == "open"
            ),
            "autoMergeRequest": (
                {"enabledAt": (auto_merge or {}).get("enabled_at") or "enabled"}
                if auto_merge else None
            ),
            "baseRef": {
                "branchProtectionRule": (
                    {
                        "requiresStatusChecks": bool(status_checks),
                        "requiredStatusCheckContexts": list(
                            status_checks.get("contexts") or [],
                        ),
                    }
                    if protection is not None else None
                ),
            },
        }

    def merge(self, repo, number, method, head, disable=False):
        # Native auto-merge enrollment has no REST equivalent; this remains
        # the sole GraphQL call site in this reconciler (DAN-3334).
        args = ["pr", "merge", str(number), "--repo", repo]
        args += ["--disable-auto"] if disable else [
            "--auto", f"--{method}", "--match-head-commit", head,
        ]
        self.run(args)


def blocker(pr, labels, checks, statuses, rules):
    if pr["state"] != "OPEN":
        return "not_open"
    if pr["isDraft"]:
        return "draft"
    if "do-not-merge" in {label.lower() for label in labels}:
        return "label_hold"
    if pr["reviewDecision"] == "CHANGES_REQUESTED":
        return "changes_requested"
    if pr["mergeable"] != "MERGEABLE":
        return "not_mergeable"
    protection = (pr.get("baseRef") or {}).get("branchProtectionRule") or {}
    required = set(protection.get("requiredStatusCheckContexts") or []) if protection.get("requiresStatusChecks") else set()
    for rule in rules:
        if rule["type"] == "required_status_checks":
            required.update(check["context"] for check in rule["parameters"]["required_status_checks"])
    if not required:
        return "no_required_checks"
    latest_statuses = {}
    for status in statuses:
        latest_statuses.setdefault(status["context"], status["state"])
    observed = {check["name"] for check in checks} | latest_statuses.keys()
    if not required.issubset(observed):
        return "missing_required_checks"
    if any(check["status"] != "completed" or check["conclusion"] not in ("success", "neutral", "skipped") for check in checks):
        return "checks_not_green"
    if any(state != "success" for state in latest_statuses.values()):
        return "statuses_not_green"
    if pr["mergeStateStatus"] != "CLEAN" and not (
        pr["mergeStateStatus"] == "BLOCKED" and pr["viewerCanEnableAutoMerge"]
    ):
        return "merge_state"
    return None


def evidence(api, repo, number):
    pr = api.pull_request(repo, number)
    rest_pr = api.rest(f"repos/{repo}/pulls/{number}")
    head_repo = (rest_pr.get("head") or {}).get("repo") or {}
    head_repository = head_repo.get("full_name")
    if not head_repository or (
        head_repository.casefold() != repo.casefold()
        and rest_pr.get("author_association") not in ("OWNER", "MEMBER", "COLLABORATOR")
    ):
        return pr, "untrusted_fork"
    if rest_pr["head"]["sha"] != pr["headRefOid"]:
        raise APIError("PR head moved between API snapshots")
    head = pr["headRefOid"]
    pages = api.rest(f"repos/{repo}/commits/{head}/check-runs?filter=latest&per_page=100", paginate=True)
    checks = [check for page in pages for check in page["check_runs"]]
    statuses = api.rest(f"repos/{repo}/commits/{head}/statuses?per_page=100", paginate=True)
    rules = api.rest(f"repos/{repo}/rules/branches/{quote(pr['baseRefName'], safe='')}?per_page=100", paginate=True)
    labels = [label["name"] for label in rest_pr["labels"]]
    return pr, blocker(pr, labels, checks, statuses, rules)


def reconcile(api, *, apply=False):
    report = {"apply": apply, "repositories": [], "pull_requests": [], "errors": 0}
    core_remaining, graphql_remaining = (0, 0)
    if hasattr(api, "rate_limit_remaining"):
        core_remaining, graphql_remaining = api.rate_limit_remaining()
    report["rate_limit"] = {"core": core_remaining, "graphql": graphql_remaining}
    # Abort before a fleet-wide walk when either shared dizhaky budget is low.
    if core_remaining and core_remaining < 100:
        report["errors"] = 1
        report["error"] = "rest_rate_limit_low"
        return report
    if graphql_remaining and graphql_remaining < 100:
        report["errors"] = 1
        report["error"] = "graphql_rate_limit_low"
        return report
    repos = api.rest("user/repos?affiliation=owner,collaborator,organization_member&per_page=100", paginate=True)
    for listed in repos:
        if listed.get("archived") or listed.get("disabled") or not (listed.get("permissions") or {}).get("admin"):
            continue
        repo = listed["full_name"]
        try:
            current = api.rest(f"repos/{repo}")
            if current.get("archived") or current.get("disabled") or not (current.get("permissions") or {}).get("admin"):
                continue
            setting = "already_enabled"
            missing_settings = {field: True for field in ("allow_auto_merge", "delete_branch_on_merge")
                                if not current.get(field)}
            if missing_settings:
                setting = "would_enable"
                if apply:
                    updated = api.rest(f"repos/{repo}", method="PATCH", body=missing_settings)
                    if any(not updated.get(field) for field in missing_settings):
                        raise APIError("Repository auto-merge/branch-cleanup settings did not enable")
                    setting = "enabled"
            report["repositories"].append({"repo": repo, "setting": setting})
            method = next((method for field, method in (
                ("allow_squash_merge", "squash"), ("allow_merge_commit", "merge"), ("allow_rebase_merge", "rebase"),
            ) if current.get(field)), None)
            prs = api.rest(f"repos/{repo}/pulls?state=open&per_page=100", paginate=True)
            for listed_pr in prs:
                # Skip drafts from the list payload — avoids a REST PR+reviews
                # round-trip that cannot enroll anyway (DAN-3334).
                if listed_pr.get("draft"):
                    continue
                number = listed_pr["number"]
                result = {"repo": repo, "number": number}
                try:
                    pr, reason = evidence(api, repo, number)
                    head = pr["headRefOid"]
                    if not reason:
                        fresh, reason = evidence(api, repo, number)
                        if fresh["headRefOid"] != head:
                            reason = "head_changed"
                        pr = fresh
                    if reason:
                        result["outcome"] = "skipped"
                        result["reason"] = reason
                        if pr.get("autoMergeRequest") and reason in ("draft", "label_hold", "changes_requested", "checks_not_green", "statuses_not_green", "untrusted_fork"):
                            if apply:
                                api.merge(repo, number, method, head, disable=True)
                            result["outcome"] = "disabled" if apply else "would_disable"
                    elif not method:
                        result.update(outcome="skipped", reason="no_allowed_merge_method")
                    elif pr.get("autoMergeRequest"):
                        result["outcome"] = "already_enrolled"
                    else:
                        if apply:
                            api.merge(repo, number, method, head)
                        result["outcome"] = "native_auto_merge_requested" if apply else "would_request_native_auto_merge"
                    result["head"] = head
                except (APIError, KeyError, TypeError, ValueError, subprocess.TimeoutExpired) as exc:
                    result.update(outcome="error", error=type(exc).__name__)
                    report["errors"] += 1
                report["pull_requests"].append(result)
        except (APIError, KeyError, TypeError, ValueError, subprocess.TimeoutExpired) as exc:
            report["repositories"].append({"repo": repo, "error": type(exc).__name__})
            report["errors"] += 1
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Apply changes; default is read-only")
    args = parser.parse_args()
    if not os.environ.get("GH_TOKEN"):
        raise SystemExit("GH_TOKEN is required; use AUTO_MERGE_PAT or GH_PAT")
    try:
        result = reconcile(GitHub(), apply=args.apply)
    except (APIError, KeyError, TypeError, ValueError, subprocess.TimeoutExpired) as exc:
        result = {"errors": 1, "error": type(exc).__name__}
    print(json.dumps(result, indent=2))
    raise SystemExit(bool(result["errors"]))


if __name__ == "__main__":
    main()
