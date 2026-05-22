# gh CLI Cheat Sheet

Synced from Obsidian `Projects/Tech/github-ops/GH-CHEATSHEET.md` (2026-05-22).

Account: **dizhaky** | gh 2.92+ | HTTPS git

## Auth & status

```bash
gh auth status
gh api user --jq '.login'
```

## Repos

```bash
gh repo list dizhaky --limit 50
gh repo view dizhaky/REPO
gh api repos/dizhaky/REPO --jq '{visibility, default_branch, delete_branch_on_merge}'
```

## PRs

```bash
gh pr list --repo dizhaky/REPO
gh pr view N --repo dizhaky/REPO --json state,mergeable,statusCheckRollup
gh pr checks N --repo dizhaky/REPO
gh pr merge N --repo dizhaky/REPO --squash --admin --delete-branch
gh pr close N --repo dizhaky/REPO --comment "Superseded by ..."
```

## Workflows

```bash
gh run list --repo dizhaky/REPO --limit 10
gh run list --status failure --limit 20
gh run view RUN_ID --repo dizhaky/REPO --log-failed
gh workflow run "Workflow Name" --repo dizhaky/REPO
```

## Dependabot / security

```bash
# Count by severity
gh api 'repos/dizhaky/REPO/dependabot/alerts?state=open&per_page=100' \
  -q 'group_by(.security_advisory.severity) | map({severity: .[0].security_advisory.severity, count: length})'

# Critical only
gh api 'repos/dizhaky/REPO/dependabot/alerts?state=open&per_page=100' \
  -q '[.[] | select(.security_advisory.severity=="critical")] | .[] | "\(.number) \(.dependency.package.name)"'

# Account-wide alert totals
gh api graphql -f query='{ viewer { repositories(first:100, ownerAffiliations:OWNER) { nodes { name vulnerabilityAlerts { totalCount } } } } }' \
  -q '[.data.viewer.repositories.nodes[] | select(.vulnerabilityAlerts.totalCount > 0)] | sort_by(-.vulnerabilityAlerts.totalCount) | .[0:10] | .[] | "\(.name): \(.vulnerabilityAlerts.totalCount)"'
```

## Repo settings (API)

```bash
gh api -X PUT repos/dizhaky/REPO/vulnerability-alerts
gh api -X PUT repos/dizhaky/REPO/automated-security-fixes
gh api -X PATCH repos/dizhaky/REPO \
  -f delete_branch_on_merge=true \
  -f allow_update_branch=true
```

## Lock check

```bash
gh api graphql -f query='{ repository(owner:"dizhaky", name:"REPO") { isLocked lockReason } }'
```

## Org

```bash
gh api user/orgs --jq '.[].login'   # JHJ-Corp (member)
```
