# Global Rules | Dan Izhaky

Policy: `~/.claude/rules/CODING-RULES.md` (Operating defaults, Karpathy). Reuse loaded policy/skills until source or scope changes. Linear: read `~/Dev/dotfiles/rules/LINEAR-WORKFLOW.md` via the `linear` skill before any Linear read/write.

## Work
- Follow task-scoped autonomy and protected-action safeguards. Credential rotation requires AskUserQuestion confirmation naming the exact target, incident or not; recommended choice first, plus defer. Preserve explicit read-only/no-ship scope, unrelated work, hooks, required CI, review, signing.
- Non-trivial work: `TASK/ASSUMPTIONS/CHECK FIRST/DONE WHEN/SCOPE`; verification: `~/.claude/refs/QC-CORE.md`. Output/optional recommendations: `~/.claude/refs/OUTPUT-FORMAT.md`.
- Findings: independent verifier agent (fresh context, refutes) per finding before report; fix loops stop after two no-progress rounds; report residue.
- Never hand Dan routine commands; run them via authorized runners, probe, verify. Ask only for human needs or protected actions.
- Merge: ready PRs, squash auto-merge armed (checks gate it; no required checks: wait for green); holds: dependency or no-ship/draft-only/manual-review; never `--admin`.

## Tools
- Owned apps: `mcp__unified-gateway__*` first; never bypass for `notionApi`/`nexus-gateway`/`claude_ai`. Refs: `~/.claude/refs/UNIFIED-GATEWAY-COOKBOOK.md`, dotfiles `mcp/MCP-CONTRACT.md`.
- Secrets: `~/.secrets.env` → Keychain → `op read`; no scanning. `op inject` needs the unlocked desktop app.
- Public web: guarded Nexus `web`: basic/3, no raw/images, extract opt-in → Context.dev → Exa/WebFetch/WebSearch; no direct Tavily plugin/MCP/auto-CLI. Links: oembed/short-link; X: `xread URL`. Browser: `browser-agent-loop`.
- Skills: route work with `skill-router`, reuse what is loaded. Memory: `memory`, hook-managed; “hold” pauses writes; context warnings ~80%/90%. Host work: `whichmachine` (else `tailscale status`).

## Services, time
- Services/daemons/cron: `~/Dev/dotfiles/rules/SERVICE-HARDENING.md` first; errors → `#infra-health` via authorized alerting. Supabase: `~/.claude/refs/SUPABASE-WORKFLOW-FULL.md`; topology: dotfiles `INFRASTRUCTURE.md`.
- Eastern (`America/New_York`, DST-aware), ISO-8601 offsets. UTC for GitHub API, cron, tool-read logs, token expiry. Session-end diary: `rules/OBSIDIAN-VAULT-FIRST.md`, `obsidian-vault-manager`.

No financial-data output (1099s, bank statements or similar); mapping, drafting and account analysis fine.
