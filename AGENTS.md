# .github — Agent context

> **Purpose:** Central GitHub templates, reusable workflows, and account hygiene. Public repo: keep everything here safe for public view.

Fleet policy: ~/Dev/dotfiles/rules/CODING-RULES.md + LINEAR-WORKFLOW.md (loaded globally).

## Fleet essentials (cloud sessions)

Cloud/web sessions here do not load the global rules, so the essentials are:

- Work autonomously to completion; confirm before destructive or irreversible actions (delete, overwrite, force-push, credential changes, spending, external sends).
- Every change goes branch → PR → required checks green → squash-merge. Never push to `main`, never `--admin`, never bypass checks.
- Linear (team DAN) is the system of record for non-trivial work.

## Stack

GitHub Actions, Python rollout scripts

## Commands

| Action | Command |
|--------|---------|
| Install | `python3 -m pip install "pytest>=8,<10"` |
| Run | `gh workflow run nightly-health-check.yml -R dizhaky/.github` |
| Test | `TZ=UTC LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONHASHSEED=0 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q tests` |
| Lint | `actionlint .github/workflows/<file>.yml` |

Template tests need pytest for import-time isolation and disposable child-process probes. CI runs pytest on pushes and PRs.

## CI

Required checks on `main`: `test` and `scan / gitleaks`. This repo is public, so its own jobs stay on GitHub-hosted `ubuntu-latest` and no self-hosted runner is registered here.

## Self-hosted runner policy (DAN-4030)

- Reusable workflows (`reusable-ci.yml`, `reusable-nightly-maintenance.yml`, `reusable-scan-failure-alert.yml`, `reusable-secret-scan.yml`) accept a `runner` input which defaults to `'"ubuntu-latest"'`.
- Repositories migrated to the self-hosted MFC3 runner (ci-runner-1, `DAN-4030`) explicitly pass `runner: '["self-hosted", "linux", "x64", "hetzner"]'` (or equivalent labels).
- Public repositories or repos without registered self-hosted runners omit `runner` to use GitHub-hosted `ubuntu-latest` without risk of sitting queued indefinitely.

## Canonical docs hosted here

- `docs/KARPATHY-RULES.md` is the canonical Karpathy rules file other repos link to. Never move or rename it.
- Test-Suite Isolation Standard: [TEST-ISOLATION.md](docs/TEST-ISOLATION.md) ([canonical](https://github.com/dizhaky/.github/blob/main/docs/TEST-ISOLATION.md)); all test suites follow it.
- System log format: `docs/system-log/README.md`. Repo templates seeded by `scripts/rollout-docs.py` live in `.github/repo-templates/`.

## GitHub-native review capture

- `.github/workflows/post-merge-review-capture.yml` records late reviews as GitHub issues using `GITHUB_TOKEN`, without webhook secrets. It does not enable hosted automatic Code Review or change merge gates.
- Supported review authors include Codex, Greptile (`greptile-apps[bot]`), Copilot, and GitHub Actions; reviewer identity is fetched from GitHub rather than trusted from the artifact.
- Requires Issues enabled and `issues: write`; skipped author replies, pre-merge reviews, and PRs that close or are titled/branched as a prior capture follow-up do not create issues. Lookup failures fail closed rather than creating duplicates.
- Syntax check: `actionlint .github/workflows/post-merge-review-capture.yml`.

## Global auto-merge reconciliation

- Default delivery policy (Dan, 2026-09-07): completed trusted harness work runs verification, merges to `main` through normal protected merging, cleans eligible merged remote branches, and verifies backend completion without asking Dan for code review or routine approval. Preserve CI, signing, conflict, security and review-resolution gates; resolve findings through the harness instead of bypassing them. Never discard dirty or unmerged local work.

- `global-auto-merge.yml` reports active personal owned/administered repositories every 30 minutes using trusted default-branch code and existing authentication. It cannot change settings or enroll PRs; organization repositories are excluded. Repository general/Dependabot workflows and templates are also read-only reporters.
- `scripts/ai_delivery.py` is the sole AI enrollment writer: bounded tool-free proposals, protected paths, hardened Git, no-force repair commits honoring configured/native signing, including verified GitHub CAS signing when natively required and local signing is disabled, actual new-head native CI, authoritative required reviews, renewable executor leases and fresh owner-created commit-status receipts. Drafts, holds and absent required CI stay held. Never execute PR scripts on the credentialed host. `scripts/launch_ai_delivery.py` verifies protected default source before each fresh single-cycle process; the prepared bootstrap installs outside Documents. See `docs/ai-delivery.md` for runtime and release gates.
- Complete contained workflow/controller evidence is readable as untrusted data; generated CI/governance/instruction writes and package test-control changes remain forbidden. Missing, incomplete or oversized evidence holds rather than truncates. Native API token fields never enter receipts. The AI receipt gates controller enrollment without changing native protections; retire other writers before activation.

## Required secret-scan callers

- Pin `.github/repo-templates/secret-scan.yml` to a reviewed full commit SHA of the reusable scanner. Update the pin deliberately after verification; do not use a moving branch reference for a required security check.
- Include the `edited` pull-request activity alongside opened/synchronize/reopened so base-branch retargeting produces a fresh diff scan.

## Documentation duty

Before finishing any non-trivial session:

1. **System log** — Append to `docs/system-log/YYYY-MM-DD.md` (Eastern ISO-8601 timestamp with `-04:00`/`-05:00`, agent/tool, repos touched, summary, commits/PRs, follow-ups). Never rewrite existing entries.
2. **Agent files** — Update this file if commands, architecture, CI, security, or gotchas changed.
3. **Obsidian** — For cross-repo or operational work, update `Projects/Tech/<topic>/` and link from [[Projects/Tech/GitHub Ops/Reference/RUNBOOKS|GitHub Ops Runbooks]].
4. **No secrets** in logs or markdown. Redact tokens and credential paths.

Skip only for typo-only or comment-only edits.

## References

- Unified Gateway Cookbook: [dotfiles canonical copy](https://github.com/dizhaky/dotfiles/blob/main/.claude/refs/UNIFIED-GATEWAY-COOKBOOK.md)
- Account runbooks: [Obsidian — GitHub Ops Runbooks](obsidian://open?vault=obsidian-vault&file=Projects/Tech/GitHub%20Ops/Reference/RUNBOOKS)
- Standards: [Obsidian — Agent Documentation Standards](obsidian://open?vault=obsidian-vault&file=Projects/Tech/Agent%20Documentation/Reference/STANDARDS)
- Central templates: [dizhaky/.github](https://github.com/dizhaky/.github)
