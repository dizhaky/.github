# dizhaky/.github

Central GitHub defaults for the **dizhaky** account: profile README, reusable workflows, PR/issue templates, and copy-paste repo templates.

## Reusable workflows

| Workflow | Purpose |
|----------|---------|
| `reusable-ci.yml` | Node (npm/pnpm/yarn) + Python lint/test/build with optional `strict` mode |
| `reusable-secret-scan.yml` | Gitleaks on every push and PR |

## Repo bootstrap

Copy files from `.github/repo-templates/` into each repository, or run the account rollout script from your automation host.

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
