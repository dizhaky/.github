## Fleet essentials (cloud sessions)

Cloud and web sessions do not load the fleet rules, so this is the minimum. Anything else in this file overrides it.

- Work autonomously to completion. Before anything destructive or irreversible (delete, overwrite, force-push, credential changes, spending, external sends), confirm first and name the exact target.
- Ship on a branch through a PR with green required checks, then squash-merge. Never push to `main`, never `--admin`, never bypass hooks or checks; when blocked, keep the work and report the exact blocker.
- Never commit secrets; redact tokens and credential paths in logs and docs.
- Linear (team DAN, prefix `DAN-`) is the system of record for non-trivial work. Branch `dan/DAN-xxx-short-description`; issue bodies follow the vault playbook `Projects/Playbooks/Linear Issue Standard.md`.
- Before working a DAN issue, post the `<!-- linear-agent-lease:v1 -->` check-in (executor, time, expiry within 6 h, scope, next checkpoint), add your harness `agent:*` label, then move it to In Progress. When you stop, post a `<!-- linear-agent-checkout:v1 -->` receipt and move it out: Done after automated verification (In Review only for an external reviewer, never to park work for Dan), Blocked with one `Waiting:*` label and the exact unblock, Todo if resumable, Backlog if paused.
- Ask Dan only through the `AskUserQuestion` menu, never inline prose, and only for a protected action or a decision that is his. State a root cause only after testing it end to end under the real conditions; until then call it a hypothesis.
- Full policy: dotfiles `rules/CODING-RULES.md` and `rules/LINEAR-WORKFLOW.md`.
