# Linear Blocked↔Wait guardian

Shipped v1 (DAN-4091, parent DAN-4090). Policy: `rules/LINEAR-WORKFLOW.md`; vault SoT `Projects/Playbooks/Linear Claim Blocked Wait.md`; IDs `.claude/refs/LINEAR-IDS.md`.

## What it does
- `.claude/scripts/linear-blocked-wait-guardian.py`, run by `session-start-wrapper.py` on Claude Code SessionStart (any harness may exec it; output is the same JSON `systemMessage` or nothing).
- Lists issues in status **Blocked**; for each with zero `Waiting:*` labels, emits one `systemMessage` naming them plus the `Waiting:*` pick-list (name + id). The legacy Wait-group label `Blocked` does not count as a why.

## Hard limits
- Warn only: no comments, no label writes, no Linear mutation of any kind. Never invent a why — the agent or Dan picks the `Waiting:*` label.
- Silent when the scan is clean or `LINEAR_API_KEY` is missing; transport errors go to stderr only.
- Never clears `Waiting:*` on status changes, never conflates executor labels with Claim, never sets Blocked on lease expiry (that is the lease guardian's Todo path, `rules/LINEAR-AGENT-LEASE-GUARDIAN.md`).

Not built: a webhook that comments at the moment of transition (needs a receiver deploy). Projects Manager remains the board-hygiene gate.
