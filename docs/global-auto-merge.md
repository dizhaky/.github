# Global owned-repository delivery reporter

`Global Auto-Merge Reconciler` retains its existing workflow identity and runs
half-hourly on the trusted default branch. It reports fully paginated active
personal owned/administered repositories, repository auto-merge settings, native
PR gates and delivery holds. Organization and unrelated administered repositories
are excluded.

The global script is read-only, including when a caller supplies its deprecated
`--apply` flag. It does not change settings, disable or enroll native requests,
merge PRs, convert drafts or update protection. The workflow retains existing
`AUTO_MERGE_PAT`/`GH_PAT` authentication for authorized reads and uploads a bounded
retained JSON report. Repository general and Dependabot workflows are read-only
reporters as well; no PR code is checked out by these reporters.

`ai_delivery.py` is the sole automated enrollment writer. A fresh executor lease,
actual current-head native CI, required native approvals, complete reviewed
findings and an owner-created commit-status receipt tied to trusted worker code
are checked before protected native auto-merge. See [AI delivery](ai-delivery.md)
for the complete repair loop, Mac runtime limits and coordinated release gates.

```sh
python3 scripts/global_auto_merge.py
TZ=UTC LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONHASHSEED=0 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q tests/test_global_auto_merge.py
```

Machine-readable stdout records exact scope, observed settings, PR dispositions
and failures. A missing credential, quota exhaustion or pagination failure is
reported as a failure, rather than an empty successful inventory. No credentials
or raw PR bodies are printed. Read-only reporting is not proof that the controller
has deployed, repaired, certified or merged a PR.
