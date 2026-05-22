# System log (account standard)

Canonical format for `docs/system-log/` in dizhaky repos.

## Purpose

Machine-readable audit trail of what agents and automation changed, when, and what follow-ups remain. Human rationale and runbooks live in Obsidian; agent context lives in `CLAUDE.md` / `AGENTS.md`.

## Layout (per repo)

```
docs/system-log/
  README.md          # points here or uses repo-templates copy
  .gitkeep           # keeps directory when empty
  YYYY-MM-DD.md      # one append-only file per UTC day
```

## Entry format

```markdown
## YYYY-MM-DDTHH:MM:SSZ — Short title (agent/tool)

- **Agent/tool:** Cursor | Claude Code | GitHub Actions | manual
- **Repos:** repo-a, repo-b
- **Done:** bullet summary of work completed
- **Commits/PRs:** abc123, #42 (optional)
- **Follow-up:** open items (optional)
```

## Rules

1. **Append only** — never rewrite history except to redact secrets
2. **No secrets** — redact tokens, API keys, passwords, credential paths
3. **UTC timestamps** — ISO-8601 with `Z`
4. **Skip trivial edits** — typos and comment-only changes do not need entries

## Automation

- **Cursor stop hook** (user-level): appends a minimal stub on agent completion when workspace is a git repo
- **Rollout:** `scripts/rollout-docs.py` seeds `docs/system-log/` and agent files from `.github/repo-templates/`
- **PR template:** checkbox in `PULL_REQUEST_TEMPLATE.md` for doc updates

## Related docs

- [[Projects/Tech/agent-documentation/STANDARDS|Agent Documentation Standards]] (Obsidian)
- [[Projects/Tech/github-ops/RUNBOOKS|GitHub Ops Runbooks]] (Obsidian)
- [[Projects/Tech/repos/INDEX|dizhaky repo index]] (Obsidian)
