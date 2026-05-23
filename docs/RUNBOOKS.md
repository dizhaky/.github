# Runbooks — dizhaky GitHub account

**Last updated:** 2026-05-23

> **Also see:** Obsidian [[Projects/Tech/github-ops/RUNBOOKS|GitHub Ops Runbooks]] and [[Projects/Tech/github-ops/DEPRECATED-REGISTRY|Deprecated Registry]] (`~/Projects/obsidian-vault/Projects/Tech/github-ops/`).

---

## Wholesale cleanup session (2026-05-23)

Account-wide hygiene pass: Dependabot merges, nightly Maintenance fixes, two repo deprecations, and documented remaining blockers.

### Merged / fixed

| Area | Outcome |
|------|---------|
| Dependabot sweep | 20+ PRs merged (mission-control, paperclip pre-deprecation, cloud-automation-hub, everything-claude-code, litellm ×13, danizhaky.com, return-runner, cah #144/#152) |
| Nightly Maintenance | Root cause: full-history gitleaks + private checkout gaps. Central fixes merged: `e81bd46` (2-day rolling scan + private token), `e3609d6` (gitleaks install retry) |
| Per-repo green re-runs | claude-mem, codex-config, kb-daemon, kb-watcher, mission-control, dotfiles, mcp-servers, obsidian-vault, litellm-hetzner-config, openclaw-monorepo (pre-archive), everything-claude-code, Organize-the-UST-onedrive-and-sharepoint |
| openclaw-monorepo (pre-deprecation) | Unarchived briefly; `monitoring/` gitignore fix; axios bump; nightly green before shutdown |
| ust-automation-scripts | Dashboard Tailwind oxide CI fix; nightly gitleaks disabled full-history scan |

### Deprecated (archived)

See [Deprecated repository registry](#deprecated-repository-registry) below.

### Remaining blockers

| Blocker | Repo | Notes |
|---------|------|-------|
| Fork CI baseline | `litellm` | Postgres service container password; CodSpeed 401 on benchmark job |
| Dependabot backlog | `litellm` | ~126 open alerts after triage; targeted uv lock bumps needed (aiohttp, next, hono, mlflow); dismiss #154 after mlflow fix on main |
| Unified-organizer build | `ust-automation-scripts` | Next/corepack `yarn@npm` clash — build excluded from CI until resolved |
| Gitleaks allowlists | `codex-config` | Session logs and vault/config repos with recent secret-shaped commits may need `.gitleaks.toml` entries |
| Open Dependabot PRs | `everything-claude-code` | ~test matrix / lockfile conflicts remain |
| CodeQL private | account | GHAS purchase required for private repo CodeQL |

System log: [docs/system-log/2026-05-23.md](./system-log/2026-05-23.md).

---

## Deprecated repository registry

| Repo | Archived | Deprecation commit | Restart runbook |
|------|----------|-------------------|-----------------|
| `dizhaky/paperclip` | 2026-05-23 | `4e9b37e7` | [paperclip-restart.md](./runbooks/paperclip-restart.md) |
| `dizhaky/openclaw-monorepo` | 2026-05-23 | `349e106971` | [openclaw-restart.md](./runbooks/openclaw-restart.md) |

Both repos are in `scripts/rollout-nightly.py` **SKIP**. Obsidian mirror: [[Projects/Tech/github-ops/DEPRECATED-REGISTRY]].

---

## OpenClaw monorepo restart

**Repo:** `dizhaky/openclaw-monorepo`  
**Status:** Deprecated and archived 2026-05-23. OpenClaw paused; monorepo preserved for restart.

### Shutdown inventory (2026-05-23)

| Item | State at shutdown |
|------|-------------------|
| Open PRs | 0 |
| In-flight workflow runs | 0 (none to cancel) |
| Deployments / environments | 0 |
| Actions secrets | 0 |
| Branch protection | Minimal (no required reviews; force-push blocked) |
| Dependabot alerts | 54 total on default branch (21 open via API); not triaged during shutdown |
| Scheduled workflows | Nightly Maintenance cron disabled via `if: github.event_name == 'workflow_dispatch'` |
| Archive | Yes — `gh repo archive dizhaky/openclaw-monorepo` |

Nested apps (`apps/openclaw-private-hank`, etc.) are deprecated at monorepo level. Separate archived repos (`openclaw`, `openclaw-infra`, `openclaw-private-hank`, `openclaw-observability`) were already archived independently.

### Restart procedure

1. **Unarchive**
   ```bash
   gh repo unarchive dizhaky/openclaw-monorepo
   ```

2. **Re-enable scheduled Nightly Maintenance** — edit `.github/workflows/nightly-maintenance.yml` on `main`: remove the `if: github.event_name == 'workflow_dispatch'` guard (added 2026-05-23).

3. **Smoke-test Actions**
   ```bash
   gh workflow run "Nightly Maintenance" -R dizhaky/openclaw-monorepo
   gh run list -R dizhaky/openclaw-monorepo --limit 3
   ```

4. **Dependabot** — triage open alerts and merge or recreate PRs:
   ```bash
   gh api repos/dizhaky/openclaw-monorepo/dependabot/alerts --jq '[.[] | select(.state=="open")] | length'
   ```

5. **Account rollout** — remove `openclaw-monorepo` from `SKIP` in `scripts/rollout-nightly.py` if nightly template rollout should resume.

6. **Docs cleanup** — update `DEPRECATED.md`, README banner, and this runbook when fully live.

**Deprecation commit on main:** `349e106971` (`docs: deprecate OpenClaw monorepo (2026-05-23)`).

Detailed runbook: [docs/runbooks/openclaw-restart.md](./runbooks/openclaw-restart.md).

---

## Paperclip restart

**Repo:** `dizhaky/paperclip`  
**Status:** Deprecated and archived 2026-05-23. Development paused; repo preserved for restart.

**Full runbook:** [docs/runbooks/paperclip-restart.md](./runbooks/paperclip-restart.md)

### Shutdown inventory (2026-05-23)

| Item | State at shutdown |
|------|-------------------|
| Open PRs | 3 closed (#12, #13, #18 — Dependabot) |
| In-flight workflow runs | 1 Release run cancelled; deprecation push did not trigger CI |
| Deployments / environments | 0 deployments; npm-canary / npm-stable environments preserved |
| Actions secrets | 0 |
| Branch protection | Minimal on `master` (no required reviews; force-push blocked) |
| Dependabot alerts | 30 total (several open); not triaged during shutdown |
| Scheduled workflows | Nightly cron + push/PR triggers commented out in 7 workflows |
| Dependabot version updates | Disabled via `updates: []` in `.github/dependabot.yml` |
| Archive | Yes — `gh repo archive dizhaky/paperclip` |

### Restart procedure (summary)

1. `gh repo unarchive dizhaky/paperclip --yes`
2. Restore `.github/dependabot.yml` updates from git history
3. Uncomment `# DEPRECATED 2026-05-23` trigger blocks in `.github/workflows/*.yml`
4. Remove `DEPRECATED.md` and README banner; commit to `master`
5. `gh workflow run nightly-maintenance.yml -R dizhaky/paperclip`
6. Triage Dependabot alerts; remove `paperclip` from `SKIP` in `scripts/rollout-nightly.py` when live

**Deprecation commit on master:** `4e9b37e7` (`docs: deprecate repo — pause CI and Dependabot (2026-05-23)`).

---

## GH_PAT — account health check (`dizhaky/.github`)

The nightly `nightly-health-check.yml` workflow scans all non-archived repos for Dependabot alerts and failed Actions runs. Private repos require a classic PAT with **`repo`** scope stored as **`GH_PAT`** in this repo.

### Add the secret

1. GitHub → **Settings** → **Developer settings** → **Personal access tokens** → **Tokens (classic)** → **Generate new token (classic)**.
2. Scopes: check **`repo`** only (full control of private repositories).
3. Copy the token once.
4. Open https://github.com/dizhaky/.github/settings/secrets/actions → **New repository secret**.
5. Name: `GH_PAT` | Value: paste token → **Add secret**.
6. Trigger manually: **Actions** → **Nightly Account Health Check** → **Run workflow**.
7. Confirm the job summary says **"Using user/repos API"** (not manifest fallback).

### Verify

```bash
gh secret list -R dizhaky/.github          # should list GH_PAT
gh workflow run nightly-health-check.yml -R dizhaky/.github
gh run list -R dizhaky/.github --workflow "Nightly Account Health Check" --limit 1
```

---

## CodeQL / GitHub Advanced Security (GHAS)

CodeQL for **private** repositories requires **GitHub Advanced Security**. GitHub Pro alone does not enable code scanning on private repos.

### Confirm GHAS is not enabled

```bash
gh api repos/dizhaky/REPO/code-scanning/default-setup
# Expected without GHAS: 403 "Code scanning is not enabled for this repository"
```

### Enablement path (cost)

| Plan | Private repo CodeQL | Typical cost |
|------|---------------------|--------------|
| GitHub Free | No | $0 |
| GitHub Pro | No (public repos only for CodeQL) | ~$4/mo |
| GHAS (per repo) | Yes | ~$49/active committer/month (list price; confirm at billing) |

**Steps to enable GHAS on a private repo:**

1. Repo → **Settings** → **Code security and analysis**.
2. Under **GitHub Advanced Security**, click **Enable** (requires billing approval).
3. Enable **Code scanning** → set up CodeQL (or copy template from `dizhaky/.github`).

### Roll out CodeQL workflow

Copy `.github/repo-templates/codeql.yml` from this repo to `repos/<name>/.github/workflows/codeql.yml`. The template header documents the GHAS requirement.

Repos without GHAS should **not** add the workflow until billing is approved — the analyze job will fail with a permissions/availability error.

---

## CLAUDE_CODE_OAUTH_TOKEN — PR review (`ust-automation-scripts`)

The **Claude Code Review** workflow gates on secret presence: when `CLAUDE_CODE_OAUTH_TOKEN` is absent, the review job is skipped.

### Status (2026-05-22)

**Enabled** — secret present on `dizhaky/ust-automation-scripts`. Open a PR to verify `check-config` passes and `claude-review` executes.

### Enable (if rotating token)

1. Obtain a Claude Code OAuth token (see [claude-code-action docs](https://github.com/anthropics/claude-code-action)).
2. Repo → https://github.com/dizhaky/ust-automation-scripts/settings/secrets/actions → **New repository secret**.
3. Name: `CLAUDE_CODE_OAUTH_TOKEN` | paste token.
4. Open a PR; **Claude Code Review** should run `check-config` (pass) and `claude-review` (execute).

### Verify

```bash
gh secret list -R dizhaky/ust-automation-scripts   # should list CLAUDE_CODE_OAUTH_TOKEN
```

When enabled, configure `allowed_bots` in the workflow if Dependabot PRs should receive reviews.

---

## Stale queued run cancellation (`nightly-health-check`)

Account health check cancels queued runs older than **45 minutes** (2700s). These workflows are **never** auto-cancelled:

- `Docker Publish`
- `Quality Gate`
- `Nightly Maintenance`

Tune via `PROTECTED_WORKFLOWS` and `QUEUED_STALE_SECONDS` in `.github/workflows/nightly-health-check.yml`.
