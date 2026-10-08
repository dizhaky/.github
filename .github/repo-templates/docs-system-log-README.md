# System log

Append-only daily log of agent and automation activity in this repo.

## File naming

- One file per Eastern (America/New_York) day: `YYYY-MM-DD.md`
- Create the file on first entry; never rewrite prior days

## Entry format

```markdown
## YYYY-MM-DDTHH:MM:SS±HH:MM — Short title (agent/tool)

- **Agent/tool:** Cursor | Claude Code | GitHub Actions | manual
- **Repos:** repo-a, repo-b
- **Done:** bullet summary of work completed
- **Commits/PRs:** abc123, #42 (optional)
- **Follow-up:** open items (optional)
```

## Rules

1. **Append only** — do not edit or delete prior entries except to redact secrets
2. **No secrets** — redact tokens, API keys, passwords, and credential file paths
3. **Eastern timestamps with an explicit offset** — new entries use `America/New_York` (DST-aware) as ISO-8601 with `-04:00` (EDT) or `-05:00` (EST), e.g. `2026-10-01T09:30:00-04:00`; no `Z` suffix and no bare `EDT`. Earlier entries stay as written (rule 1). Technical UTC stays UTC: GitHub API timestamps, cron expressions, tool-consumed log formats, token expiry
4. **One session, one entry** — merge related work from the same session into a single entry

## When to log

Log after any non-trivial session: feature work, bug fixes, CI changes, refactors, rollouts, or multi-file edits.

Skip for typo-only or comment-only changes.

## Canonical spec

Account-wide standards live in [dizhaky/.github `docs/system-log/README.md`](https://github.com/dizhaky/.github/blob/main/docs/system-log/README.md) and Obsidian [[Projects/Tech/Agent Documentation/Reference/STANDARDS|Agent Documentation Standards]].
