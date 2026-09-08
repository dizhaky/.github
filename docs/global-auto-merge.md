# Global native auto-merge reconciler

`Global Auto-Merge Reconciler` runs every 15 minutes and supports manual dispatch
on this repository's default branch. It discovers **all active repositories the
credential administers**, including organization repositories, and re-enables
`allow_auto_merge` and `delete_branch_on_merge` when either setting drifts or a
new repository appears. GitHub deletes eligible merged remote head branches;
the reconciler never deletes local branches/worktrees or unmerged branches.

The workflow uses `AUTO_MERGE_PAT`, falling back to `GH_PAT`. The credential needs
repository administration for the setting and sufficient read/merge access for
PRs. It is exposed only to the trusted reconciler step, never to a PR checkout.
Missing credentials and API/pagination failures fail the run visibly.

## PR policy

Every open PR is evaluated, but native merge enrollment requires a known head
repository and either a same-repository branch or GitHub's server-provided
`OWNER`, `MEMBER`, or `COLLABORATOR` author association. External contributors'
forks and deleted/unknown head repositories are reported as `untrusted_fork`;
the harness must first validate outsider contributions and prepare a trusted
branch rather than accepting their self-reported CI. This adds no human-review
gate. Repository and PR lists, check runs, status histories, and branch rules
are fully paginated.

A PR must be open, non-draft, conflict-free, and free of a `do-not-merge` label or
changes-requested review. The target must have named required status checks in
classic branch protection or an active ruleset. Each required check must have
registered, and **all observed checks and latest status contexts** must be green.
The reconciler re-fetches the PR, protection, labels, and CI immediately before
acting and refuses a changed head.

Eligible PRs use `gh pr merge --auto --match-head-commit` with an allowed merge
method. This queues native auto-merge when GitHub still requires reviews, or
merges an already-ready protected PR. There is no `--admin`, force push, branch
deletion command, protection update, or bot-login allowlist. Existing native
requests are disabled when a draft/label/review/CI/trusted-origin hold is observed.

Unprotected targets, targets without named required checks, unknown mergeability,
missing checks, pending/failed checks, and other ineligible states are explicitly
reported as skipped. Enabling a repository setting does not mean its PRs bypass
these gates. Configure real required checks to opt a branch into automatic
merging; this workflow does not create or weaken protection rules.

GitHub enforces configured required checks at merge time. Optional checks can
change after a snapshot; put every merge-critical check into branch protection.
The schedule is eventual reconciliation, not a real-time guarantee. A token
permission loss, suspended Actions schedule, or GitHub outage is reported rather
than interpreted as an empty successful scan.

## Verification and preview

```sh
python3 scripts/global_auto_merge.py          # read-only, requires GH_TOKEN
python3 scripts/global_auto_merge.py --apply  # changes repository settings / PRs
TZ=UTC LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONHASHSEED=0 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q tests/test_global_auto_merge.py
```

Machine-readable stdout records the combined state of both repository settings
and each PR's outcome,
including explicit skip/error reasons. No token values or PR bodies are printed.
