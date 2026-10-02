# Owned repository AI delivery

`scripts/ai_delivery.py` is the sole automated PR enrollment writer. It discovers
all active personal repositories owned and administered by the authenticated
GitHub user. Organization repositories, external head repositories, archived or
disabled repositories, drafts, explicit holds and active executor leases stay
held. Existing repository CI, security checks, reviews and signing remain native
merge gates. Repository workflows and the scheduled global reconciler only report
state; they cannot independently reuse an old AI receipt to enroll a PR.

## Detect, repair, test and review

The controller paginates repository, PR, check, status, review and inline-comment
reads. Latest status per context determines whether CI failed. Pending CI waits;
actual failures can receive a bounded repair while required reviews are pending.
Clean certification and enrollment require authoritative native approval when
branch protection or a ruleset requires approving or code-owner reviews.

Codex receives bounded file content, diffs, native CI evidence and complete review
comments as untrusted evidence in an empty temporary directory. The model returns
a strict JSON proposal with whole-file content and original SHA256 hashes. It has
no shell, web, image, MCP, app, plugin, hook or agent tools. Strict installed CLI
configuration and a JSONL event allowlist reject unexpected capabilities, errors
and tool calls. The existing ChatGPT subscription supports the background
application's `gpt-5.5` model on Codex 0.154.0; the configured session model is not
changed. Unsupported `gpt-6.1-sol` CLI inference was observed and is not treated as
a successful backend. Engine authentication stays with the existing Codex login;
GitHub and signing environment variables are removed from model subprocesses.

The credentialed parent validates every patch before writing. Paths must be
canonical, relative and free of symlink escapes; case aliases, duplicate targets,
Git metadata, CI, governance, instructions, credentials and secret-like content
are rejected. Materialization and staging disable Git hooks, filesystem monitors,
configured clean/smudge/process filters, submodule recursion and file/ext protocol
execution. PR scripts are never executed on the Mac. Tests run through the
repository's actual required native CI, using its existing permissions.

A repair gets a second independent clean AI review, current-head and ownership
checks, a commit honoring configured/native signing and a normal no-force push to the original
branch. It then waits for actual CI on that new SHA. No success receipt is issued
for a merely proposed repair or a new head whose native tests have not passed.
Repositories without real required checks stay held.

On a clean, tested head, fresh native gates and the complete review digest are
checked again. Only individually identified, proven satisfied review threads can
be resolved; reviews are never dismissed or self-approved. The controller records
native before/after evidence and posts an owner-created **commit status** named
`AI Delivery / verified`, bound to the exact head, full review digest and trusted
default-branch worker revision. Same-name Actions check runs cannot substitute for
this receipt. Only this AI context is excluded from its own CI precheck. All other
required checks and their app bindings are preserved. Receipt-only diagnostic
guards are not enrollment authority and do not ignore unrelated pending CI.

Immediately before normal protected `gh pr merge --auto --match-head-commit`, the
controller rechecks active ownership, head, lease, native approvals and receipt.
It preserves an existing merge request's method; otherwise it selects an allowed
method. It restores `allow_auto_merge` only for a verified eligible owned PR if
needed, then verifies the setting. It never uses admin merge, force push, draft
conversion or a protection bypass. Actual queued/merged state is re-read.

## Renewable executor ownership

The trusted read adapter consumes fixed comment `5960945356` in private owned
`dizhaky/github-infra#49`. It verifies the private repository's admin authority,
the exact comment/issue, authenticated author's login **and ID**, updated time,
payload timestamp and a maximum age of 4500 seconds. The comment body is:

```text
<!-- ai-delivery-ownership-v1 -->
{"leasesVerifiedAt":"<UTC timestamp>","leases":[{"repo":"dizhaky/example","branch":"*","expiresAt":"<UTC timestamp>"}]}
```

An existing GitHub/Linear cloud automation refreshes this fixed comment hourly
from live executor claims. `branch: "*"` holds every PR in the named repository;
ambiguous relevant claims must conservatively cover each owned repository. A
stale, malformed, unauthorized or unreadable feed holds delivery. No local command
can make old ownership evidence fresh by merely rewriting its timestamp.
Native PR creation or update newer than the snapshot also holds until the next
automated refresh, including new repair heads. This conservative chronology guard
may add up to one hourly refresh before certification; it never treats an older
feed as proof of executor ownership for new activity.

## Run and operate

From a clean checkout of the trusted default branch, read-only inspection is:

```sh
python3 scripts/ai_delivery.py --state-dir "$DELIVERY_STATE" --policy scripts/ai-delivery-policy.json --report "$DELIVERY_REPORT" --budget 5
```

Without `--apply`, inspection cannot clone PRs, invoke AI or write GitHub state.
Applied delivery adds `--apply`; `--daemon --poll-seconds 900` repeats safely for a
fixed deployed revision. The state directory is mode 0700, with a process lock,
SQLite attempt/cursor/evidence state and permanent JSONL receipts. Attempts are
bounded to 2 per head and 4 per PR per day, with a 900-second cooldown, 1–5 PRs per
cycle and conservative REST/GraphQL quota checks. Repository read failures are
recorded separately so a broken repository cannot starve other owned repositories.
Provider diagnostics retain event types, usage and error reasons without prompts,
tool arguments or credential values. Unknown mutation outcomes are not retried.

The parent release installs the Mac LaunchAgent using existing authentication,
absolute runtime paths, persistent state and bounded rotated stdout/stderr logs.
Its single-cycle launcher must load a clean, verified default-branch revision anew
after a safe update; pulling Git beneath an already running Python daemon does not
reload imported code. Signing follows Git configuration or a live native signature
requirement: either requires `-S`, with the existing key. A locked signer holds only
that target; configured unsigned repositories follow their existing default without
an unsigned override. Native signature policy is re-read before push; new signature
requirements hold an already unsigned commit. Native CI works independently, but AI repair and
certification require the Mac awake and connected. Restart/sleep resume uses the
durable cursor and attempt ledger.

## Coordinated release gates

The parent is the only remote writer for this implementation. Before activation,
ship the controller and every legacy reporter transformation through protected
PRs, verify the exact live no-tool backend and feed, verify existing signing, and
exercise a real repair/new-head CI/review/receipt/native merge cycle, honoring the
target signing policy. Retire
all legacy enrollment paths, including templates, and disarm previously armed
native requests during the coordinated cutover. Then union the AI status into
existing required checks while preserving all existing app bindings and protections.
File presence and mocked tests do not prove deployment or a successful live loop.

The local implementation's tests and runtime receipts are recorded in the parent
`rewrite/manifests/central.json`. Deployment, target-specific signing unblock and the live complete
cycle remain explicit release gates, not claims made by this source change.
