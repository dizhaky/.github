# Linear Agent Lease Guardian

Operational contract for the hourly read-mostly stale-work sweep. The canonical lifecycle remains `rules/LINEAR-WORKFLOW.md`.

## Implementation

- Repo-owned: `bin/linear-agent-lease-guardian` (dry run by default; `--apply` writes), run hourly by LaunchAgent `launchd/com.danizhaky.timer.linear-lease-guardian.plist` on the `crm-runner` host only (one sweeper fleet-wide; `scripts/install/launchd-sync.sh` skips it elsewhere). Tests: `tests/test_linear_agent_lease_guardian.py`.
- It replaced the Codex app automation `linear-agent-lease-guardian` (DAN-3501 L3). That definition vanished from `~/.codex/automations` on every Mac, so no sweep ran and nothing alerted (DAN-4250).
- `agent:human` alone does not make an issue eligible. A latest checkout on an issue still In Progress counts as an expired lease (Todo only).
- Failures and actions go to `#infra-health` through `bin/slack-alert-infra-health.sh`.

## Eligibility

- Team: Dan's Projects.
- Status: In Progress.
- At least one routing label matching `agent:*`.
- Human-only work without an agent routing label is out of scope.

## Lease clock

- Parse only immutable `<!-- linear-agent-lease:v1 -->` check-in/renewal comments and `<!-- linear-agent-checkout:v1 -->` checkout comments.
- The latest valid check-in owns the lease; its `Lease expires` timestamp is authoritative and may be at most 6 hours after check-in.
- `updatedAt is not a lease renewal`; label, cycle, priority, description and unrelated comment edits do not extend a lease.
- For a legacy In Progress issue with no valid marker, apply a **24-hour migration grace** from its latest `updatedAt`. This fallback is migration-only, not the steady-state lease signal.

## Sweep algorithm

1. List all In Progress issues with selected fields and exhaust pagination.
2. Keep only `agent:*` issues and fetch their comments using bounded pages.
3. Classify each as current, expired, legacy-grace, malformed or unreadable. A malformed/unreadable lease fails closed and is reported; it is not moved.
4. Before any write, fetch the exact issue and latest comments again. This **compare-before-write** step must confirm the issue is still In Progress and the lease/checkout identity is unchanged; otherwise skip it.
5. For an unchanged expired lease (or expired legacy grace), move the issue to Todo and append an immutable guardian checkout comment naming the prior executor, expiry, reason and resume action. If either write fails, report the partial result; never conceal it.
6. The guardian must **never move an issue to Done**, In Review, Blocked or Backlog automatically. Those states require executor evidence or judgment.
7. Never change assignee, priority, estimate, cycle, project, labels, relations, due date, description or checklist state (the Polar handback below is the one label exception).

## Polar handback router (DAN-4388)

Same hourly run, code in `bin/linear-polar-handback` (tests: `tests/test_linear_polar_handback.py`). It replaces the model judgment that re-queued finished browser work to Polar (DAN-4269 ping-pong).

- Eligible: team DAN, label `agent:polar`, state Todo or In Review, title without `[STANDING]`.
- Polar comments are recognised by their first text line (after any marker) starting `Polar` AND an author that is Dan's own Linear user (Polar posts as Dan); bot actors, integrations and external users never trigger or block a handback (spoofed `Polar:` text is a prompt-injection path).
- Hand back when the latest Polar comment ends `Result: need` / `Result: cannot` (Ask, Try, Reply; DAN-4682), has a `For Claude Code` line, or carries the legacy `Result: blocked` / `Result: refused`, and no later non-Polar comment starts a `For Polar:` step. Polar swaps the claim itself under the new contract; the router is the backstop.
- Action: swap the claim `agent:polar` -> `agent:claude-code`, move to Todo, post one `<!-- linear-polar-handback:v1 -->` comment naming the trigger. Compare-before-write as above. This swap is the only label write either sweep makes.
- The hourly Claude Code scheduled task "Polar answer desk" (`portable-skills/polar-browser-delegate/ANSWER-DESK.md`) then answers the ask with one `For Polar:` comment and puts `agent:polar` back, or sets Blocked + Waiting:Dan and sends Dan one Slack DM when only Dan can act (MFA/SSO, a password, money, a native app, a decision). Re-queue to Polar only with a new `For Polar:` comment.

## Output and failure behavior

- **No-op runs** are silent.
- Notify only when an issue was checked out, a malformed lease needs repair, a read/write failed, or user action is required.
- Report scanned/current/legacy/expired/moved/skipped/error counts and issue identifiers for actions only; do not include private issue bodies or credentials.
- Tool/auth/pagination uncertainty fails closed: make no status changes and surface the exact failure.

## Manual dry run

Perform steps 1–3 only, emit counts and candidates, and make zero mutations. A dry run must precede activation or any guardian prompt change.
