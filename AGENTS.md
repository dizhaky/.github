# .github — Agent context

> **Purpose:** Central GitHub templates, reusable workflows, and account hygiene

## Stack

GitHub Actions, Python rollout scripts

## Commands

| Action | Command |
|--------|---------|
| Install | `n/a` |
| Run | `gh workflow run nightly-health-check.yml -R dizhaky/.github` |
| Test | `python3 -m unittest discover -s tests -p "test_*.py"` |
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
- Requires Issues enabled and `issues: write`; skipped author replies and pre-merge reviews do not create issues. Lookup failures fail closed rather than creating duplicates.
- Tests: `python3 -m unittest discover -s tests -p "test_*.py"`; syntax: `actionlint .github/workflows/post-merge-review-capture.yml`.

- Template tests require pytest (`python3 -m pip install "pytest>=8,<10"`) for disposable child-process isolation probes. CI runs unittest discovery on pushes and PRs.
