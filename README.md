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
