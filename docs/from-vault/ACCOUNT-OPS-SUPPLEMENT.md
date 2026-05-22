# Account ops supplement (from vault)

Evergreen procedures from Obsidian `Projects/Tech/github-ops/RUNBOOKS.md`. Pair with [RUNBOOKS.md](../RUNBOOKS.md) for secret setup and GHAS.

**Agent principles:** [Karpathy's Four Rules](../KARPATHY-RULES.md).

## Rollout new repo hygiene

Use the rollout script at `/tmp/github-rollout.py` (regenerate from `~/Dev/.github` templates if missing):

```bash
python3 /tmp/github-rollout.py
```

Skips: `.github`, locked repos (`isLocked: true`).

Manual single-repo rollout:

1. Copy `secret-scan.yml` and `dependabot.yml` from `dizhaky/.github/.github/repo-templates/`
2. Enable settings via API:

```bash
gh api -X PUT repos/dizhaky/REPO/vulnerability-alerts
gh api -X PUT repos/dizhaky/REPO/automated-security-fixes
gh api -X PATCH repos/dizhaky/REPO -f delete_branch_on_merge=true -f allow_update_branch=true
```

## Fix secret-scan startup_failure

**Symptom:** Workflow shows `startup_failure`, zero jobs.

**Cause:** Reusable workflow caller missing `permissions`.

**Fix:** Ensure caller has:

```yaml
permissions:
  contents: read
  pull-requests: read
jobs:
  scan:
    permissions:
      contents: read
      pull-requests: read
    uses: dizhaky/.github/.github/workflows/reusable-secret-scan.yml@main
```

Redeploy template to all repos after fixing `dizhaky/.github`.

## Branch protection (solo dev)

**Policy:** No required PR reviews on any `dizhaky` repo. Optional CI/status checks only.

- Canonical doc: [BRANCH-PROTECTION.md](../BRANCH-PROTECTION.md)
- Verify: `python3 ~/Projects/.github/scripts/verify-no-pr-reviews.py` (exit 0 = PASS)

Remove reviews on one branch:

```bash
gh api -X DELETE "repos/dizhaky/REPO/branches/BRANCH/protection/required_pull_request_reviews"
```

## Merge Dependabot PRs (solo dev)

No review gate — merge normally after CI is green:

```bash
gh pr merge N --repo dizhaky/REPO --squash --delete-branch
```

Use `--admin` only if a legacy rule or org ruleset still blocks merge. If PR is **CONFLICTING**, close it and bump dependency manually on `main`.

## Critical CVE triage

1. List alerts: `gh api 'repos/dizhaky/REPO/dependabot/alerts?state=open&per_page=100'`
2. Check `first_patched_version` — if `null`, no upstream fix yet; document and monitor
3. Bump in lockfile/requirements, commit, push
4. Re-check after ~15 min (Dependabot re-scan lag)

## Unlock agent-starter-pack

Repo locked with `lockReason: MOVING`. User action required:

1. GitHub → Settings → Repositories → agent-starter-pack → Unlock (or wait for transfer to complete)
2. Re-run rollout script for that repo only

## Nightly automation

Central workflows in `dizhaky/.github`:

| Workflow | Schedule | Purpose |
|----------|----------|---------|
| `nightly-health-check.yml` | 06:00 UTC daily | Account-wide alert/run scan; cancels stale queued runs (>45 min), skips protected workflows |
| `reusable-nightly-maintenance.yml` | workflow_call | Per-repo: gitleaks full scan, alert summary, optional auto-fix PR |

Per-repo opt-in: copy `nightly-maintenance.yml` from repo-templates (rolled out via `scripts/rollout-nightly.py`).

### Setup (one-time)

1. Add **`GH_PAT`** secret to `dizhaky/.github` — classic PAT with `repo` scope (see [RUNBOOKS.md](../RUNBOOKS.md))
2. Enable **auto-merge** in repo Settings → General → Pull Requests
3. Run rollout: `cd ~/Dev/.github && python3 scripts/rollout-nightly.py`
4. Manual trigger:

```bash
gh workflow run nightly-health-check.yml -R dizhaky/.github
gh workflow run nightly-maintenance.yml -R dizhaky/mission-control -f auto-fix=true
```

### Auto-fix behavior

- **PR-based:** `ruff check --fix`, `npm audit fix` / `pnpm audit --fix` → opens `bot/nightly-*` branch
- **Auto-merge:** `dependabot-auto-merge.yml` merges patch/minor actions bumps when CI green
- **Not auto-fixed:** major semver bumps, conflicting lockfiles, alerts with no upstream patch

### AI review on bot/nightly PRs

Wire Claude review for `bot/nightly-*` and Dependabot PRs. Example `if:` guard:

```yaml
if: >-
  github.event.pull_request.user.login == 'github-actions[bot]' ||
  startsWith(github.head_ref, 'bot/nightly-') ||
  startsWith(github.head_ref, 'dependabot/')
```

Requires `CLAUDE_CODE_OAUTH_TOKEN` or `ANTHROPIC_API_KEY`. See `ust-automation-scripts` and `cloud-automation-hub` workflows for reference implementations.
