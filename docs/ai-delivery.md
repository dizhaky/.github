# Owned repository AI delivery

`scripts/ai_delivery.py` is the sole automated PR enrollment writer. It discovers
all active personal repositories owned and administered by the authenticated
GitHub user. Every live authority check binds the returned repository name and
owner login/ID, so transferred-repository redirects hold before writes. Organization repositories, external head repositories, archived or
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

Codex receives complete bounded file content, diffs, native CI evidence and review
comments as untrusted evidence in an empty temporary directory. Read-only evidence
can include workflow, controller, governance and instruction files; it never
executes them. Canonical paths, root containment and symlink checks still apply,
and Git/authentication directories, credential files and secret-like content hold
the review. Native patches must contain complete unified hunks whose counts match
the API metadata, and current file blobs must match the native blob hash. Missing
or unsupported patches, incomplete counts and oversized evidence hold instead of
silently truncating. Limits are 25 changed files, 80KB per file or patch, 12KB per
diagnostic/comment and 180KB for the complete context. Every failed check is
included. Candidate diffs disable external diff and textconv execution.
The model returns
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
are rejected for generated writes. Package scripts and recognized test/coverage
controls cannot change; dependency-only manifest repairs remain allowed. All
patches are validated before any file write. Native API decoding removes
`temp_clone_token` recursively before evidence, reports or receipts, and model
inputs select only necessary fields. Materialization and staging disable Git hooks, filesystem monitors,
configured clean/smudge/process filters, submodule recursion and file/ext protocol
execution. PR scripts are never executed on the Mac. Tests run through the
repository's actual required native CI, using its existing permissions.

A repair gets a second independent clean AI review, current-head and ownership
checks, and a commit honoring configured/native signing on the original branch.
Before a local push it refreshes the PR and lease again, refuses changed head refs
or draft/hold boundaries, and checks signing against the current target branch.
A configured signer uses the existing key and a normal no-force Git push. If
native signatures are required but Git signing is not configured, the existing
authenticated GitHub API creates a signed commit using `expectedHeadOid`. This
route accepts only exact staged regular `100644` files and verifies the complete
tree, sole parent, owner identity, signature and branch ref independently. Unknown
write outcomes are never retried. Default-branch PR heads, including reverse PRs,
are held before any write. It then waits for actual CI on that new SHA. No success receipt is issued
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
The controller does not require this AI status to be installed as a native required
context. It enforces the AI receipt in its own enrollment path; existing native
protections stay unchanged. This is logical controller enforcement, so other
enrollment paths must be retired before activation. Repositories with no native
required check contexts remain held even if optional CI passes.

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

The prepared `scripts/launch_ai_delivery.py` verifies the exact known owner login
and ID, active admin authority, the repository default branch, protection, required
native CI/app bindings and required commit signature before code execution. It
uses hardened Git to fetch without checkout, pins and checks the exact clean SHA,
atomically installs a revision directory, then repeats native source verification.
Only regular controller/policy files inside that checkout can execute. Optional
scheduled reporter checks do not replace or deadlock required source CI. No repo
install commands run. The controller runs in a new process group each cycle;
its 2400-second timeout terminates its whole process group before releasing locks.

The parent release installs the reviewed pinned bootstrap bundle under
`~/.local/share/codex-ai-delivery`, with
`~/Library/LaunchAgents/com.dizhaky.ai-delivery.plist`; task artifacts remain in
`rewrite/runtime/` for review. There is no runtime dependency on Documents access.
The LaunchAgent uses existing authentication, absolute binaries and paths, a
900-second interval, permanent SQLite/JSONL state and stdout/stderr rotation at
5MiB with 5 retained segments. The prepared bootstrap hashes its four trusted
helper files before importing them; no authentication/configuration files are
copied. Protected updates load a new controller process from the verified default
revision; pulling Git beneath a running daemon does not reload imported code.
The LaunchAgent calls the launcher, which explicitly passes `--apply` to the
controller. The launcher itself has no `--apply` argument.
Configured signing requires `-S` with the existing key; a locked configured signer
holds its target. Native-required signatures with configured signing disabled use
the verified GitHub signing route described above. Other repositories follow
their existing default without an unsigned override. Native signature policy is
re-read before push, and configured signing is re-read before the server route; new signature
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
native requests during the coordinated cutover. Keep native protection settings
exact. Automatic approval review rejected the proposed fleet required-context
rewrite because it would persistently change protections with an unregistered
app binding before deployment and could block the fleet. That proposal is not a
release step and must not be executed or bypassed. The prepared controller can
operate against existing native checks, but it does not provide server-enforced AI
gating. Remaining live legacy runs and existing armed merge requests need explicit
cutover verification by the parent before logical controller enrollment starts.
File presence and mocked tests do not prove deployment or a successful live loop.

The local implementation's tests and runtime receipts are recorded in the parent
`rewrite/manifests/central.json`. The parent verified a real GitHub-signed task
branch commit in Organize with its existing authentication, exact tree and owner
signature; its protected default branch stayed unchanged. Deployment and a live
complete cycle remain release gates, not claims made by this source change.

## Reproducible bundle and exact-head readiness (DAN-4466)

`ai_delivery.py --repo dizhaky/example --pr 123 --head <40-char-head> --budget 1`
selects only that exact owned PR/head for one cycle. All three selector fields are
mandatory together; partial/invalid input, a returned PR identity mismatch or a
changed head blocks without trying another PR. `--daemon` is incompatible with a
selector. Dry-run remains the default: omit `--apply`. Existing native protection,
review, receipt, signature, ownership and freshness gates still apply. A repair
that changes the head returns waiting for native CI; the next targeted invocation
must deliberately select and verify that new SHA.

From a clean committed protected-default source, `scripts/ai_delivery_bundle.py
--output <new-review-directory>` prepares eight regular runtime files and a
versioned manifest: source SHA, file SHA256 hashes and absolute existing Python/gh
executables. Output is deterministic for the same source and binary paths. It does
not install or start anything. The plist starts Python with `-I -B` so bundle files cannot shadow stdlib imports.
The pinned bootstrap verifies the manifest hash and
every runtime file before importing the launcher. Unexpected files, symlinks,
changed content and untracked/dirty source fail closed. No authentication files
or credentials are copied.

After protected publication and explicit operational authorization, `--install
--bundle <reviewed-directory> --manifest-sha256 <reviewed-hash>` verifies live
protected-default source/CI/required signatures and requires its revision to equal
the manifest before and after materialization. It creates only the current user's
`~/.local/share/codex-ai-delivery` and
`~/Library/LaunchAgents/com.dizhaky.ai-delivery.plist`; existing installations and
symlink paths are preserved and refused. Installation never invokes launchctl.
The plist is unloaded, RunAtLoad false, interval 900 seconds, budget 1; loading it
is a separate applying operation. Private mode-0700 directories retain source,
SQLite/JSONL evidence and rotated logs. The activation request must explicitly
name MacBook Pro, user danizhaky, service com.dizhaky.ai-delivery, reviewed manifest
hash/source revision and intended eligible-repository scope. Inspect any disabled
allow_auto_merge target before authorizing setting restoration.

`--activate` separately rechecks the trusted source and bootstraps only this
user service, then verifies its exact executable, ordered arguments and installed plist in
native launchctl readback. Do not run it before coordinated writer retirement, genuine ownership
clearance and the exact-head protected canary. `--uninstall` is the service-only
rollback: verify installed and loaded identity, unload only that exact label,
verify absence and remove only its matching plist. An already-unloaded service is
handled through an explicit native not-found result. All runtime code, receipts
and state are retained; unrelated sessions/services/files are untouched. If a
source race leaves a partial, unloaded installation, preserve it for inspection;
do not delete/retry over existing contents automatically. No automatic reinstallation
or legacy-writer restoration is a rollback step.

These artifacts make activation reviewable; tests and prepared bundles do not
prove installation, completed AI review or a live protected delivery cycle.
