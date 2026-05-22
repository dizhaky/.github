# .github

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

## Do / Don't

- **Do:** Read `docs/system-log/` for recent changes before large refactors.
- **Do:** Update this file when commands, architecture, CI, or env vars change.
- **Don't:** Commit secrets. Redact tokens and credential paths in logs and docs.

## Documentation duty

Before finishing any non-trivial session:

1. **System log** — Append to `docs/system-log/YYYY-MM-DD.md` (UTC timestamp, repos touched, summary, commits/PRs, follow-ups).
2. **Agent files** — Update `CLAUDE.md` and/or `AGENTS.md` if commands, architecture, CI, security, or gotchas changed.
3. **Obsidian** — For cross-repo or operational work, update a note under `Projects/Tech/` and link from [[Projects/Tech/github-ops/RUNBOOKS|GitHub Ops Runbooks]].
4. **No secrets** in logs or markdown.

Skip only for typo-only or comment-only edits.

## References

- System log format: `docs/system-log/README.md`
- Account runbooks: [Obsidian — GitHub Ops Runbooks](obsidian://open?vault=Documents&file=Projects/Tech/github-ops/RUNBOOKS)
- Standards: [Obsidian — Agent Documentation Standards](obsidian://open?vault=Documents&file=Projects/Tech/agent-documentation/STANDARDS)
- Central templates: [dizhaky/.github](https://github.com/dizhaky/.github)
