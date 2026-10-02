# .github — Agent context

> **Purpose:** Central GitHub templates, reusable workflows, and account hygiene

## Stack

GitHub Actions, Python rollout scripts

## Commands

| Action | Command |
|--------|---------|
| Install | `n/a` |
| Run | `gh workflow run nightly-health-check.yml -R dizhaky/.github` |
| Test | `TZ=UTC LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONHASHSEED=0 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q tests` |
| Lint | `n/a` |

## Tooling

- **Cursor rules:** `.cursor/rules/karpathy-four-rules.mdc` — required always-on Karpathy four rules ([canonical](https://github.com/dizhaky/.github/blob/main/docs/KARPATHY-RULES.md)); install: `~/Dev/dotfiles/cursor/bin/install-karpathy-repo-rules.sh`
- **Test Isolation:** All test suites follow the [Test-Suite Isolation Standard](docs/TEST-ISOLATION.md) ([canonical](https://github.com/dizhaky/.github/blob/main/docs/TEST-ISOLATION.md))
- **Skills:** Repo-specific skills in `.cursor/skills/` or user-level `~/.cursor/skills-cursor/`
- **MCP:** Configure per project; never log tokens or credentials

## Documentation duty

Before finishing any non-trivial session:

1. **System log** — Append to `docs/system-log/YYYY-MM-DD.md` (UTC timestamp, agent/tool, repos touched, summary, commits/PRs, follow-ups).
2. **Agent files** — Update `CLAUDE.md` and/or this file if commands, architecture, CI, security, or gotchas changed.
3. **Obsidian** — For cross-repo or operational work, update `Projects/Tech/<topic>/` and link from [[Projects/Tech/github-ops/RUNBOOKS|GitHub Ops Runbooks]].
4. **No secrets** in logs or markdown.

Skip only for typo-only or comment-only edits.

## References

- Test-Suite Isolation Standard: [TEST-ISOLATION.md](docs/TEST-ISOLATION.md) ([canonical](https://github.com/dizhaky/.github/blob/main/docs/TEST-ISOLATION.md))
- Unified Gateway Cookbook: [dotfiles canonical copy](https://github.com/dizhaky/dotfiles/blob/main/.claude/refs/UNIFIED-GATEWAY-COOKBOOK.md)
- System log format: `docs/system-log/README.md`
- Account runbooks: [Obsidian — GitHub Ops Runbooks](obsidian://open?vault=obsidian-vault&file=Projects/Tech/GitHub%20Ops/01_Reference/RUNBOOKS)
- Standards: [Obsidian — Agent Documentation Standards](obsidian://open?vault=obsidian-vault&file=Projects/Tech/Agent%20Documentation/01_Reference/STANDARDS)
- Central templates: [dizhaky/.github](https://github.com/dizhaky/.github)

## GitHub-native review capture

- `.github/workflows/post-merge-review-capture.yml` records late reviews as GitHub issues using `GITHUB_TOKEN`, without Hermes or webhook secrets. It does not enable hosted automatic Code Review or change merge gates.
- Supported review authors include Codex, Greptile (`greptile-apps[bot]`), Copilot, and GitHub Actions; reviewer identity is fetched from GitHub rather than trusted from the artifact.
- Requires Issues enabled and `issues: write`; skipped author replies, pre-merge reviews, and PRs that close or are titled/branched as a prior capture follow-up do not create issues. Lookup failures fail closed rather than creating duplicates.
- Tests: `TZ=UTC LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONHASHSEED=0 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q tests`; syntax: `actionlint .github/workflows/post-merge-review-capture.yml`.

- Template tests require pytest (`python3 -m pip install "pytest>=8,<10"`) for import-time isolation and disposable child-process probes. CI runs pytest on pushes and PRs.

## Global auto-merge reconciliation

- Default delivery policy (Dan, 2026-09-07): completed trusted harness work runs verification, merges to `main` through normal protected merging, cleans eligible merged remote branches, and verifies backend completion without asking Dan for code review or routine approval. Preserve CI, signing, conflict, security and review-resolution gates; resolve findings through the harness instead of bypassing them. Never discard dirty or unmerged local work.

- `global-auto-merge.yml` reports active personal owned/administered repositories every 30 minutes using trusted default-branch code and existing authentication. It cannot change settings or enroll PRs; organization repositories are excluded. Repository general/Dependabot workflows and templates are also read-only reporters.
- `scripts/ai_delivery.py` is the sole AI enrollment writer: bounded tool-free proposals, protected paths, hardened Git, no-force repair pushes honoring configured/native signing, actual new-head native CI, authoritative required reviews, renewable executor leases and fresh owner-created commit-status receipts. Drafts, holds and absent required CI stay held. Never execute PR scripts on the credentialed host. See `docs/ai-delivery.md` for runtime and release gates.

## Required secret-scan callers

- Pin `.github/repo-templates/secret-scan.yml` to a reviewed full commit SHA of the reusable scanner. Update the pin deliberately after verification; do not use a moving branch reference for a required security check.
- Include the `edited` pull-request activity alongside opened/synchronize/reopened so base-branch retargeting produces a fresh diff scan.

## Self-hosted runner policy (DAN-4030)

- Reusable workflows (`reusable-ci.yml`, `reusable-nightly-maintenance.yml`, `reusable-scan-failure-alert.yml`, `reusable-secret-scan.yml`) accept a `runner` input which defaults to `'"ubuntu-latest"'`.
- Repositories migrated to the Hetzner self-hosted runner infrastructure (MFC3 / ci-runner-1, `DAN-4030`) explicitly pass `runner: '["self-hosted", "linux", "x64", "hetzner"]'` (or equivalent labels).
- Public repositories or repos without registered self-hosted runners omit `runner` to use GitHub-hosted `ubuntu-latest` without risk of sitting queued indefinitely.
