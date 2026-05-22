# Runbooks — dizhaky GitHub account

**Last updated:** 2026-05-22

> **Also see:** [from-vault/](./from-vault/) — Obsidian-synced cheatsheet and account-ops supplement (rollout, branch protection, nightly automation).

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
