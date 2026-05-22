# dizhaky/.github

Central GitHub defaults for the **dizhaky** account: profile README, reusable workflows, PR/issue templates, copy-paste repo templates, and shared agent coding principles.

## Agent coding principles

All dizhaky repos and automation should follow **[Karpathy's Four Rules](docs/KARPATHY-RULES.md)** (think first, stay simple, surgical edits, verify goals). Copy into any repo:

- **Cursor rule:** `.cursor/rules/karpathy-four-rules.mdc` (included in this repo)
- **Bootstrap template:** `.github/repo-templates/cursor-rules-karpathy.mdc`
- **Canonical dotfiles install:** `~/Dev/dotfiles/cursor/rules/karpathy-four-rules.mdc` → `~/.cursor/rules/`

## Reusable workflows

| Workflow | Purpose |
|----------|---------|
| `reusable-ci.yml` | Node (npm/pnpm/yarn) + Python lint/test/build with optional `strict` mode |
| `reusable-secret-scan.yml` | Gitleaks on every push and PR |
| `reusable-nightly-maintenance.yml` | Full secret scan, alert report, optional auto-fix PR (ruff/audit) |
| `nightly-health-check.yml` | **Scheduled** account-wide health scan (06:00 UTC); needs `GH_PAT` secret |

## Nightly automation

| Template | Destination | Purpose |
|----------|-------------|---------|
| `nightly-maintenance.yml` | `.github/workflows/` | Per-repo nightly maintenance (06:30 UTC) |
| `dependabot-auto-merge.yml` | `.github/workflows/` | Auto-merge safe github-actions Dependabot PRs |
| `codeql.yml` | `.github/workflows/` | Weekly CodeQL (requires GHAS on private repos) |

**Secrets:** Add `GH_PAT` (classic, `repo` scope) to this repo for cross-repo account health checks. Per-repo workflows use `GITHUB_TOKEN`. See **[docs/RUNBOOKS.md](docs/RUNBOOKS.md)** for GH_PAT, GHAS/CodeQL, and optional Claude review setup.

**Vault sync:** Operational supplements from Obsidian `Projects/Tech/github-ops/` live in **[docs/from-vault/](docs/from-vault/)** (cheatsheet, rollout, nightly automation).

## Repo bootstrap

Copy files from `.github/repo-templates/` into each repository, or run the account rollout script from your automation host.

| Template | Destination in consumer repo |
|----------|------------------------------|
| `ci.yml`, `secret-scan.yml`, `dependabot.yml` | `.github/workflows/` or `.github/` |
| `cursor-rules-karpathy.mdc` | `.cursor/rules/karpathy-four-rules.mdc` |

## Consumer example

```yaml
jobs:
  ci:
    uses: dizhaky/.github/.github/workflows/reusable-ci.yml@main
    with:
      node-version: "22"
      package-manager: pnpm   # or auto
      strict: false
```
