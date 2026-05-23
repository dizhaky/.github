# Paperclip restart procedure

Runbook for bringing [dizhaky/paperclip](https://github.com/dizhaky/paperclip) back online after the 2026-05-23 deprecation pause.

## Pre-restart inventory

```bash
gh repo view dizhaky/paperclip --json isArchived,defaultBranchRef
gh pr list -R dizhaky/paperclip --state open
gh run list -R dizhaky/paperclip --limit 5
gh api repos/dizhaky/paperclip/dependabot/alerts --jq 'map(select(.state=="open")) | length'
gh secret list -R dizhaky/paperclip
```

## 1. Unarchive (if archived)

Archiving matches the account pattern used for `openclaw-infra` (read-only pause). Unarchive before any writes:

```bash
gh repo unarchive dizhaky/paperclip --yes
```

## 2. Restore Dependabot

In `.github/dependabot.yml`, replace `updates: []` with the commented ecosystems (github-actions, npm, docker). See git history before the deprecation commit or copy from `.github/repo-templates/dependabot.yml` in dizhaky/.github.

```bash
cd ~/Projects/paperclip
git log -1 --oneline -- .github/dependabot.yml  # find pre-deprecation SHA
git show <sha>:.github/dependabot.yml
```

After merge to `master`, Dependabot will resume on its weekly schedule. Optionally trigger immediately:

```bash
gh api repos/dizhaky/paperclip/dependabot/updates -X POST 2>/dev/null || true
```

## 3. Re-enable GitHub Actions workflows

Each workflow under `.github/workflows/` has a `# DEPRECATED 2026-05-23` block. Restore original `on:` triggers:

| Workflow | Restore |
|----------|---------|
| `nightly-maintenance.yml` | Uncomment `schedule` cron |
| `release.yml` | Uncomment `push` on `master` |
| `docker.yml` | Uncomment `push` on `master` / tags |
| `refresh-lockfile.yml` | Uncomment `push` on `master` |
| `secret-scan.yml` | Uncomment `push` and `pull_request` |
| `pr.yml` | Uncomment `pull_request` on `master` |
| `dependabot-auto-merge.yml` | Uncomment `pull_request` types |

`e2e.yml` and `release-smoke.yml` were already `workflow_dispatch`-only — no change.

Remove `workflow_dispatch`-only stubs added during deprecation where they duplicate restored triggers.

## 4. Remove deprecation notices

- Delete or rewrite `DEPRECATED.md`
- Remove the deprecation banner from `README.md`

Commit to `master` (normal push triggers will resume once triggers are restored).

## 5. Verify CI

```bash
# Manual smoke after triggers restored
gh workflow run nightly-maintenance.yml -R dizhaky/paperclip

# Watch latest runs
gh run list -R dizhaky/paperclip --limit 10
gh run watch -R dizhaky/paperclip  # pass latest run ID
```

Optional:

```bash
gh workflow run e2e.yml -R dizhaky/paperclip -f skip_llm=true
gh workflow run release-smoke.yml -R dizhaky/paperclip -f paperclip_version=canary
```

## 6. Dependabot PRs

- Re-open closed Dependabot PRs only if branches still exist; otherwise wait for new weekly PRs
- Review open security alerts: `gh api repos/dizhaky/paperclip/dependabot/alerts --jq '.[] | select(.state=="open") | {number, package: .security_vulnerability.package.name, severity: .security_advisory.severity}'`

## Preserved across pause (do not recreate unless intentional)

- Repository secrets (none configured at deprecation)
- Branch protection on `master` (minimal rules; no required reviews)
- Workflow files and environments (`npm-canary`, `npm-stable`)
- Git history and tags

## Deprecation reference

- Shutdown date: **2026-05-23**
- In-repo notice: `DEPRECATED.md` on paperclip (removed on restart)
- System log: `docs/system-log/2026-05-23.md` in dizhaky/.github

## Related

- [[Projects/Tech/github-ops/RUNBOOKS|GitHub Ops Runbooks]] (Obsidian)
- Account archived repo pattern: `openclaw-infra` in `scripts/rollout-nightly.py`
