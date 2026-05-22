# Branch protection — dizhaky account policy

**Last updated:** 2026-05-22

## Policy (solo developer)

| Setting | Value |
|---------|--------|
| Required PR reviews | **Off** — no `required_pull_request_reviews` on any default branch |
| Required approving review count | **0** (block must be absent, not merely zero) |
| Optional status checks | Allowed (CI, secret scan, etc.) |
| Admin merge | Direct push and `--admin` merge allowed when needed |

Rationale: single-owner repos do not benefit from mandatory human review gates; optional CI and secret scanning remain the quality bar.

## Scope

- **Personal account (`dizhaky`):** all non-archived repositories, default branch plus `main` / `master` when they differ.
- **Org (`JHJ-Corp`):** not managed here; org rulesets require GitHub Team (403 on API). Apply the same policy manually if org repos are added later.

## Remove required reviews (one branch)

```bash
gh api -X DELETE "repos/dizhaky/REPO/branches/BRANCH/protection/required_pull_request_reviews"
```

## Verify account-wide

From this repo:

```bash
python3 scripts/verify-no-pr-reviews.py
```

Exit code `0` only when:

- `required_approving_review_count > 0` count is **0**
- No branch still exposes `required_pull_request_reviews`
- No active ruleset contains `pull_request` / `required_reviewers` rules

## Rulesets

If a repo uses **rulesets** instead of classic branch protection:

```bash
gh api "repos/dizhaky/REPO/rulesets"
gh api "repos/dizhaky/REPO/rulesets/RULESET_ID"
```

Edit or disable rulesets that enforce PR reviews (`type`: `pull_request`, `required_reviewers`).

## History

- **2026-05-22:** Removed `required_pull_request_reviews` from 22 protected branches across 22 repos (verification PASS).
