# .github — Agent context

> **Purpose:** Central GitHub templates, reusable workflows, and account hygiene

## Stack

GitHub Actions, Python rollout scripts

## Commands

| Action | Command |
|--------|---------|
| Install | `n/a` |
| Run | `gh workflow run nightly-health-check.yml -R dizhaky/.github` |
| Test | `python3 scripts/verify-no-pr-reviews.py` |
| Lint | `n/a` |

## Tooling

- **Cursor rules:** `.cursor/rules/karpathy-four-rules.mdc` — required always-on Karpathy four rules ([canonical](https://github.com/dizhaky/.github/blob/main/docs/KARPATHY-RULES.md)); install: `~/Dev/dotfiles/cursor/bin/install-karpathy-repo-rules.sh`
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

- Unified Gateway Cookbook: [UNIFIED-GATEWAY-COOKBOOK.md](file:///Users/danizhaky/.claude/refs/UNIFIED-GATEWAY-COOKBOOK.md)
- System log format: `docs/system-log/README.md`
- Account runbooks: [Obsidian — GitHub Ops Runbooks](obsidian://open?vault=Documents&file=Projects/Tech/github-ops/RUNBOOKS)
- Standards: [Obsidian — Agent Documentation Standards](obsidian://open?vault=Documents&file=Projects/Tech/agent-documentation/STANDARDS)
- Repo index: [Obsidian — dizhaky repos](obsidian://open?vault=Documents&file=Projects/Tech/repos/INDEX)
