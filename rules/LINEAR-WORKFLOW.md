# Linear Workflow — all harnesses (CANON)

**Workspace:** dizhaky · **Prefix:** DAN-. Overrides older recipes, cached IDs, template defaults; safety and user scope govern. Refs: `~/.claude/refs/LINEAR-IDS.md` (IDs), `~/.claude/refs/LINEAR-WORKFLOW-FULL.md` (FULL ref: removed detail, receipt templates, URLs, UI recipes, cloud-harness ingestion).

## Tracking
Linear is the task system of record for owner, status, priority, dependencies, commitments, evidence; Obsidian holds context; `TASKS.md` is a dated mirror, never a competing database. Every non-trivial actionable deliverable needs an issue (Q&A, lookups, trivial edits do not). Search before creating; **no project per session**, no duplicates or artificial subtasks. Continue only the requested scope: suggestions, labels or tracking updates never authorize unrelated execution, cloud inference, spending, credential changes or destructive actions.

## Access
Read via gateway nexus `dispatch` only (issues/projects/documents; get/search; `id` not `issue_id`). Native Linear MCP skips compress-on-retrieve; do not call it. Never invent tools, reconfigure auth, or print/copy secrets. Read the exact issue/project first (filters, small pages, selected fields, full pagination); discover IDs live, never hard-code a cycle ID. Access failure → scoped local checklist + the narrow unblock; never invent an ID, claim a remote write or mark work Done.

## Start of work
1. Read the issue/project, native dependencies, vault context, `TASKS.md`; sync the mirror.
2. Reuse the right project/initiative; first state scope, assumptions, baseline, risks, ordered acceptance criteria (multi-part work: gates + baseline/intended-field manifests).
3. One issue = one independently verifiable deliverable; checkboxes for steps; sub-issues only for separate owners, lifecycles, deadlines, dependencies.
4. In Progress only when work starts with prerequisites/authorization met; planning-only or paused stays Backlog, outside the cycle.

## Issue contract
- Title `[Domain/scope] Verifiable outcome`; correct project; domain/routing labels; accountable assignee; priority **1–4**; estimate **1/2/3/5**; split anything larger.
- Dan is accountable owner, not automatically executor; preserve delegation. `agent:human` only when the next action genuinely needs Dan.
- Description: this skeleton. One owner per checklist line, by name (Dan, a named agent, Polar, the cloud agent), never "we". Real `- [ ]` boxes, checked (moved to Already done, with proof) only after the step passes, never for attempted/planned work.

```markdown
## Outcome
What is true when this is done, in one short paragraph.
## Already done
- [x] What shipped, with the proof. Owner: name.
## Blocked on
The single current blocker, or "None."
## Checklist
- [ ] Concrete step. Owner: name.
- [ ] QC, including harden. Owner: name.
## Owners
- Name: the steps they own.
## Non-goals
What this issue will not change.
```

- New work starts in Backlog. Todo only after the design is approved. In Progress only when execution starts, with an agent lease comment. Browser work: Todo `agent:polar` + `## Outcome` + `For: Polar Browser (agent:polar)`/Harness/Project/Trace + `#polar-tasks` (`polar-browser-delegate`); done→In Review→Done after verify; need/cannot→Todo+`agent:claude-code` (~5min/desk). Done only after QC passes, including harden, not because a pull request exists. The agent's finish is not enough.
- Native relations only for real dependencies. Reuse the four issue templates (defaults Backlog/Medium/Dan/2; set final values explicitly).
- Urgent `dueDate` needs a real deadline or named review date, recorded; never fabricate or silently downgrade recovery/security urgency. No fitting project → record a routing exception.

## Hierarchy, Claim/Blocked/Wait
- Milestones are acceptance checkpoints. Never auto-close a project on issue count, 100% progress or empty queue; verify outcome, unresolved work, final health; preserve history; surface open issues in completed containers.
- Priority (impact, not enthusiasm): 1 urgent outage/time-sensitive risk/deadline · 2 important commitment/blocking prerequisite · 3 normal · 4 optional. States: Backlog uncommitted · Todo accepted · In Progress executing · In Review awaiting external review · Done verified.
- Current cycle = realistic commitments, one active deliverable per executor; no cycle-automation changes or bulk priority rolls without scoped authorization.
- Fail-closed (vault SoT: `Projects/Playbooks/Linear Claim Blocked Wait.md`): exactly one Claim-group `agent:*` before substantive work (incl. `agent:polar`); executor labels separate, optional; host-lane: Claim = owning bot, tag executor on code runs. Blocked → **status** `Blocked` + one `Waiting:*` why-label + exact unblock comment + native dependency when one exists; never invent a why; clear it on unblock/Done. Never park Dan work in In Review. Unknown step → stop, ask or comment the gap. Chat todos are scratch.

## Agent work lease — mandatory check-in and checkout
Starting an `agent:*` issue opens a **6 hours** lease. Check in before or with the In Progress move (status alone is not a check-in): a `<!-- linear-agent-lease:v1 -->` comment, Lease expires: ≤6h out; renew only with a new comment, never edit/delete a receipt; `updatedAt` is not a renewal. On stopping, post `<!-- linear-agent-checkout:v1 -->` and leave In Progress: **Done** after automated verification passes (no human gates); In Review only for external review; Blocked per the map; Todo when resumable; Backlog when paused/decommitted. Long-running ops stay In Progress only on an unexpired, renewed lease.

Guardians: hourly lease sweep (24-hour migration grace; must re-read before mutating; never auto-completes; expired → Todo + audit); SessionStart warns on Blocked without `Waiting:*` (never applies one; legacy `Blocked` label does not count). Rule files: `rules/LINEAR-AGENT-LEASE-GUARDIAN.md`, `rules/LINEAR-BLOCKED-WAIT-GUARDIAN.md`.

## Completion
1. Perform independent verification of the real outcome: parse actual results, check every intended identity/field, re-check after fixes. An API response, merged PR or exit 0 alone is not proof.
2. Update the description (date, before/after table, checked items moved to Already done, links, deviations, next steps; keep blocked/unverified work open) + a completion comment (Linear documents or permissioned links, not only `file://`).
3. Only then mark **Done** and read it back. Code: `Fixes DAN-xxx` on the PR, harness branch convention; never bypass required review, merge authorization or outcome tests.
4. Session end: sync `TASKS.md`, append the system log, post project health; no new issue unless backlog execution was requested.

```markdown
## QC Verification
- Method:
- Scope:
- Before:
- After:
- Verdict: PASS/FAIL
```

## Memory Gateway receipt gate
Search first; preserve prior versions of living facts. Project state, decisions or commitments need a `PREF::` / `PERSON::` / `DECISION::` / `PROJ::` / `PLAYBOOK::` / `REF::` memory; carry the returned `memory_id` into the issue update or final report. An existing `memory_id` from the required pre-write search is an acceptable receipt when the fact is unchanged. Otherwise record `Memory Gateway: N/A` or `Memory Gateway: blocked (<unblock>)`. A vault/TASKS update or Linear comment alone is not enough. Never write secrets.

## Safety
Read before write; change only intended fields; preserve labels, relations, owners, histories, unrelated work; snapshot before broad metadata changes. Deletion, overwriting unrelated/user content, archival, force-push, credential rotation, purchases and external sends need exact-target approval; stop there. Routine tested commits, pushes, PRs and CI-gated merges are already authorized by CODING-RULES; tracking permissions never substitute for protected-action approval.

## Entry views
Current commitments · Blocked (filter = status) · Waiting on Dan (`agent:human`) · Unowned. URLs: FULL ref. Cloud harnesses without local file access need this contract injected; generated files/symlinks prove coverage, not ingestion — verify ingestion separately.
