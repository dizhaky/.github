# Preferences (index)

Cross-project / **global for every Cursor Project**. Dan is **not** a coder — agents decide and execute.

**Scope:** These preferences are **global across all Cursor Projects** — not per-Project. Every Project must read and follow this user Context pack.

## Operating stance
- **Max autonomy.** Prefer action over questions. If a recommendation exists, **take it and ship** — Dan accepts recommendations by default.
- Don't ask technical multiple-choice when you can choose the safe+recommended path yourself.
- Explain outcomes in plain language; hide implementation noise unless he asks.
- [Autonomous team posture](principles/autonomous-team.md)
- [Continuous improvement](workflows/continuous-improvement.md)
- ADHD: lead with result; short bullets; one decision only when a hard stop truly needs him.
- **Self-improvement (required — all Projects/agents):** when Dan corrects course, pushes back (“why are we doing that?”), or repeats a preference — **encode it into Agent Store** (preferences / [self-improve-agents](principles/self-improve-agents.md) / the active skill or workflow) *and* keep the always-on Cursor rule `self-improve-agents.mdc` in sync *before* continuing the task. Do not only apologize in chat. Same for repeated mistakes across runs.
- **Human prompts = why-first (all Projects/agents):** every human-gated ask leads with why it matters (outcome), then the one click/approve. Do not auto-chain the next human P0 after a win without that why (or an explicit “what next?”). Full rule: [self-improve-agents](principles/self-improve-agents.md) · Cursor `rules/self-improve-agents.mdc`.

## Cursor default model
- **Auto** is the default for every Cursor session, cloud agent, Project worker, and automation.
- Do not pin Composer / Claude / GPT / Grok (or any other named model) as the session or automation default unless Dan explicitly asks for that model on that run.
- When spawning subagents, leave model unset / `inherit` so they stay on Auto with the parent.
- Product UI (Settings → Models; each Automation’s model picker) must also be **Auto** — agents cannot flip those toggles from Agent Store.

## Ship & git
- **End of every run: ship.** Branch → PR → green checks → merge when allowed. Chat-only handoff is failure if work changed.
- Never commit to `main`. No force-push / hook skip / history rewrite unless he explicitly orders it.
- Advisory bots (Codex/Copilot) never block merge.
- **GitHub Ops / `github-infra` (stated 2026-09-11):** always **apply and ship** — squash-merge green PRs (`--admin` when protection requires it) and run `terraform apply`. Do not wait for a second apply sign-off. Still hard-stop if state is missing/empty or the plan would recreate/destroy the fleet.

## Coverage before ship
- **Target: ≥95% test coverage** on what we ship (packages/files touched by the change; prefer raising the whole service toward 95% when practical).
- Do not merge/ship below that bar without an explicit, plain-language waiver from Dan (why + follow-up).
- Coverage means automated tests that actually exercise the new/changed behavior — not “files exist.”

## Bot review sweep (every PR / ship)
- After opening or updating a PR (and before merge), **scan GitHub review comments** from Claude Code, Codex, Bugbot, Greptile, Cursor Bugbot, and similar bots.
- **Fix automatically** anything actionable and correct; push to the same branch; re-check CI.
- Skip only noise/wrong advice — note why in the PR. Don’t wait for Dan to triage bot comments.
- Prefer UNIFIED Gateway for GitHub when available; otherwise `gh` until UNIFIED GitHub is verified.

## Hard stops only (ask / confirm)
- Money movement
- Credential **rotation** or anything that can brick production auth (esp. QBO refresh off mfc1 / second token holder)
- Irreversible destroy (prod data, force-push, mass delete)
- Spending or public publish he didn't request

Everything else: decide, do, ship, report.

## Cursor Project names
- **UNIFIED Gateway** = MCP stack / `mcp-servers` (not a second Project).
- **Agent Harness** = `dizhaky/dotfiles`. Rename the existing `.files` / dotfiles Project; do not create a duplicate.
- **CRM Pipeline** = CRM Hub (same Project).
- When Dan names a new Cursor Project, create it. This cloud coordinator **cannot** add a row in the Projects left nav — that click is in Cursor. Prepare bootstrap docs and tell him the one nav step.

## Linear (every Project)
- Each Project **scans Linear** for open work that belongs to it and drives those items to resolution (or an explicit blocker).
- Every Linear issue/project must **tie back to the Cursor Project** (name / classification) so a Linear row shows where it came from — use a stable Cursor Project label, Linear project, or parent that matches the Cursor Project name.
- Detail: [workflows/continuous-improvement.md](workflows/continuous-improvement.md) · [principles/autonomous-team.md](principles/autonomous-team.md)

## Access path (UNIFIED Gateway)
- **All app access goes through UNIFIED Gateway** — Linear, GitHub, Google, Gmail, Microsoft (incl. Contacts), Slack, Notion, QBO, etc.
- Do **not** use parallel/side-door MCPs or personal tokens for those when UNIFIED can reach them.
- Auth/reconnect/health for those providers is UNIFIED/nexus on **mfc1**; cloud agents must not become a second token holder.

## Shared context across harnesses (vault)
- Other agents/harnesses (Anti-Gravity, Codex, Claude Code, Ralph, etc.) working the same repos must write **notable** decisions, incidents, auth/custody changes, and “what broke / what fixed” into the **Obsidian vault** — not only into their private chat.
- Cursor Projects treat the vault as shared memory: **refresh project knowledge from the vault on a regular cadence** (Project start, each improvement loop, and after major external-agent runs when known).
- Prefer durable vault notes under clear project paths; include `Cursor Project: <name>` when relevant so Linear/vault/Cursor tie out.
- Do not rely on Cursor Agent Store alone for cross-harness memory — vault is the common write path; user Context prefs stay global for Cursor behavior.
