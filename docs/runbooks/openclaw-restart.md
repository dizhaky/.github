# OpenClaw monorepo restart procedure

Runbook for bringing [dizhaky/openclaw-monorepo](https://github.com/dizhaky/openclaw-monorepo) back online after the 2026-05-23 deprecation pause.

## Pre-restart inventory

```bash
gh repo view dizhaky/openclaw-monorepo --json isArchived,defaultBranchRef
gh pr list -R dizhaky/openclaw-monorepo --state open
gh run list -R dizhaky/openclaw-monorepo --limit 5
gh api repos/dizhaky/openclaw-monorepo/dependabot/alerts --jq 'map(select(.state=="open")) | length'
gh secret list -R dizhaky/openclaw-monorepo
```

## 1. Unarchive

Archiving matches the account pattern used for `openclaw-infra` and `openclaw-private-hank` (read-only pause). Unarchive before any writes:

```bash
gh repo unarchive dizhaky/openclaw-monorepo --yes
```

## 2. Re-enable scheduled Nightly Maintenance

In `.github/workflows/nightly-maintenance.yml`, remove the deprecation guard on the `maintenance` job:

```yaml
# Remove this line (added 2026-05-23):
if: github.event_name == 'workflow_dispatch'
```

The `schedule` cron (`30 6 * * *`) and `workflow_dispatch` inputs remain in the file — no other trigger changes needed.

CI, Secret Scan, and Dependabot Auto-Merge workflows were left unchanged; they resume automatically once the repo is unarchived.

## 3. Remove deprecation notices

- Delete or rewrite `DEPRECATED.md`
- Remove the deprecation banner from `README.md`

Commit to `main`.

## 4. Verify CI

```bash
gh workflow run "Nightly Maintenance" -R dizhaky/openclaw-monorepo
gh run list -R dizhaky/openclaw-monorepo --limit 10
gh run watch -R dizhaky/openclaw-monorepo  # pass latest run ID
```

## 5. Dependabot

- Review open alerts (54 on default branch at shutdown; 21 open via API):
  ```bash
  gh api repos/dizhaky/openclaw-monorepo/dependabot/alerts --jq '.[] | select(.state=="open") | {number, package: .security_vulnerability.package.name, severity: .security_advisory.severity}'
  ```
- Merge or recreate PRs as needed; root `.github/dependabot.yml` (github-actions weekly) was not modified during shutdown.

## 6. Account rollout (optional)

Remove `openclaw-monorepo` from `SKIP` in `dizhaky/.github/scripts/rollout-nightly.py` and update deprecation comments in `scripts/repo-manifest.txt` and `rollout-docs.py`.

## Nested apps (monorepo level)

Deprecation was at monorepo level only. Separate archived repos still exist independently:

| Repo | Status |
|------|--------|
| `dizhaky/openclaw` | Archived (subtree: `apps/openclaw/`) |
| `dizhaky/openclaw-infra` | Archived (subtree: `infra/openclaw-infra/`) |
| `dizhaky/openclaw-private-hank` | Archived (subtree: `apps/openclaw-private-hank/`) |
| `dizhaky/openclaw-observability` | Archived (subtree: `apps/openclaw-observability/`) |

Restart those separately if needed; unarchiving the monorepo does not unarchive them.

## Preserved across pause (do not recreate unless intentional)

- Repository secrets (none configured at deprecation)
- Branch protection on `main` (minimal rules; force-push blocked)
- Workflow files and git history (subtree history intact)
- Nested app directories under `apps/` and `infra/`

## Deprecation reference

- Shutdown date: **2026-05-23**
- Deprecation commit: `349e106971` on `main`
- In-repo notice: `DEPRECATED.md` (remove on restart)
- System log: `docs/system-log/2026-05-23.md` in dizhaky/.github

## Related

- [[Projects/Tech/github-ops/RUNBOOKS|GitHub Ops Runbooks]] (Obsidian)
- Account archived repo pattern: `scripts/rollout-nightly.py` SKIP set
