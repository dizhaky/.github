#!/usr/bin/env python3
"""Verify dizhaky repos have no required PR reviews on protected branches."""

from __future__ import annotations

import json
import subprocess
import sys

OWNER = "dizhaky"


def gh_json(*args: str):
    r = subprocess.run(["gh", "api", *args], capture_output=True, text=True)
    if r.returncode != 0:
        return None
    return json.loads(r.stdout)


def main() -> int:
    lines = subprocess.run(
        [
            "gh",
            "api",
            "user/repos",
            "--paginate",
            "-q",
            f'.[] | select(.owner.login=="{OWNER}" and .archived==false) | [.name, .default_branch] | @tsv',
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip().split("\n")

    repos = [tuple(l.split("\t", 1)) for l in lines if l]
    count_gt_zero: list[str] = []
    rpr_present: list[str] = []
    ruleset_hits: list[str] = []
    failures: list[str] = []

    for name, default in repos:
        branches = {default, "main", "master"}
        for branch in branches:
            prot = gh_json(f"repos/{OWNER}/{name}/branches/{branch}/protection")
            if prot is None:
                continue
            rpr = prot.get("required_pull_request_reviews")
            if not rpr:
                continue
            label = f"{name}/{branch}"
            rpr_present.append(label)
            if rpr.get("required_approving_review_count", 0) > 0:
                count_gt_zero.append(label)

        rulesets = gh_json(f"repos/{OWNER}/{name}/rulesets") or []
        for rs in rulesets:
            if rs.get("enforcement") not in ("active", "evaluate"):
                continue
            rid = rs["id"]
            full = gh_json(f"repos/{OWNER}/{name}/rulesets/{rid}")
            if full is None:
                failures.append(f"fetch ruleset {name}/{rid}")
                continue
            for rule in full.get("rules", []):
                if rule.get("type") in ("pull_request", "required_reviewers"):
                    ruleset_hits.append(f"{name} ruleset {rid} ({rs.get('name')})")

    print("=== verify-no-pr-reviews ===")
    print(f"Repos scanned (non-archived): {len(repos)}")
    print(f"required_approving_review_count > 0: {len(count_gt_zero)}")
    for x in count_gt_zero:
        print(f"  - {x}")
    print(f"required_pull_request_reviews present: {len(rpr_present)}")
    for x in rpr_present:
        print(f"  - {x}")
    print(f"ruleset PR review rules: {len(ruleset_hits)}")
    for x in ruleset_hits:
        print(f"  - {x}")
    print(f"API failures: {len(failures)}")
    for x in failures:
        print(f"  - {x}")

    ok = not count_gt_zero and not rpr_present and not ruleset_hits
    print(f"Verdict: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
