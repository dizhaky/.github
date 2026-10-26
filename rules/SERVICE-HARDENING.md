# Service Hardening Rules

**Applies to:** every long-running service, daemon, container, cron job or watchdog you build.
**Origin:** 2026-04-18 Hetzner incidents — disk hit 100% (no build-cache pruning, no container log caps; supabase-db, paperclip-server, firecrawl-api crashed together) and nexus-gateway restarted 28,569 times (orphan held port 8002; no `ExecStartPre` preemption or `StartLimitBurst`).

## 1. The service MUST cap its own disk use
Never rely on external rotation.
- **Logs:** logrotate with a sane policy, or cap at the emitter (e.g. Python `RotatingFileHandler` 50MB × 3).
- **Docker:** `daemon.json` sets `log-opts: max-size=50m, max-file=3`; every deploy doc verifies it.
- **Build caches** (BuildKit, uv, pip, npm) never expire by default: schedule weekly `docker builder prune -af --filter until=168h` (CI/CD or cron) wherever you deploy.
- **Temp files:** `mktemp` + `trap`, or `/tmp` with `systemd-tmpfiles` aging. Never accumulate in `$HOME` or `/var`.

## 2. Ports MUST be preempted, not assumed free
Every unit that binds a port includes:

```ini
[Unit]
StartLimitIntervalSec=300
StartLimitBurst=10

[Service]
ExecStartPre=/usr/bin/bash -lc '/usr/bin/fuser -k -TERM <PORT>/tcp >/dev/null 2>&1 || true'
ExecStartPre=/usr/bin/bash -lc 'for i in $(seq 1 15); do /usr/bin/fuser <PORT>/tcp >/dev/null 2>&1 || exit 0; sleep 1; done; /usr/bin/fuser -k -KILL <PORT>/tcp >/dev/null 2>&1; sleep 2; ! /usr/bin/fuser <PORT>/tcp >/dev/null 2>&1'
KillMode=mixed
KillSignal=SIGTERM
TimeoutStopSec=30
```

`StartLimit*` belong in `[Unit]` (ignored under `[Service]`). The first probe sends SIGTERM so the 15s grace loop is meaningful; the final probe fails the start loudly if the port is still held after SIGKILL.

Orphans (manual runs, tmux detach, SSH drop) survive `systemctl stop` and hold the port; without preemption the unit crash-loops.

## 3. `StartLimitBurst` is non-negotiable
Cap restarts (see §2) so systemd marks the unit `failed` and the watchdog escalates, instead of looping thousands of times unnoticed.

## 4. Health endpoints MUST be cheap and honest
`GET /health` → `200 {"status":"ok"}` when healthy; no auth; non-200 when a dependency (DB, upstream) is unreachable — never a lying 200; <100ms, no side effects.

## 5. Watchdogs MUST survive what they monitor
Every `scripts/watchdog*.sh` has:
- `flock` against overlapping runs on timer replay;
- journald fallback for `log()` when the disk is full (`echo >>file || logger -t …`);
- self-log rotation (`mv $LOG $LOG.1` at 10MB);
- a timeout on every external call (`timeout 10 docker …`, `curl -m 8 …`);
- fallback alerting when Slack fails: `logger -p daemon.crit` (rsyslog → Falcon);
- webhook validation — an empty/404 webhook is a failure, not success;
- a dependency liveness probe (`docker info` before any `docker inspect` loop).

## 6. `sudo -n` needs an explicit sudoers grant
A non-root script that restarts system services gets a minimal grant, validated with `visudo -cf`; never rely on undefined sudo behavior:

```
# /etc/sudoers.d/<service>-watchdog
<user> ALL=(root) NOPASSWD: /bin/systemctl restart <specific-unit>.service, …
```

**Caveat:** inside a user namespace that does not map host uid 0 (e.g. mfc1's shell gateway), sudo refuses to run (`sudo must be owned by uid 0 …`) and no sudoers grant helps. Diagnose with `stat -c %u /usr/bin/sudo` (65534 = host root unmapped). The polkit path, its traps (`manage-unit-files` implies more and cannot be unit-scoped; prefer `manage-units`) and the bus checks: `.claude/refs/USERNS-SUDO-POLKIT.md`. Provider rescue route: skill `host-sudo-via-rescue`.

## 7. Timers need jitter
`[Timer]` blocks include `RandomizedDelaySec=60` or more; `Persistent=true` without jitter replays every missed run at once.

## 8. Ship checklist
Every new service ships with, and records in its `README.md` or `DEPLOY.md` (per `~/Dev/dotfiles/rules/SERVICE-HARDENING.md`):
- [ ] systemd unit with port preemption, `KillMode`, `StartLimitBurst`
- [ ] `/health` endpoint live
- [ ] log rotation (app-level or `logrotate.d`)
- [ ] watchdog entry (`~/scripts/watchdog-services.sh` on Hetzner, or the Mac equivalent)
- [ ] sudoers grant for restart, if needed
- [ ] documented shutdown procedure (no orphans)
- [ ] Linear issue for any monitoring gap
- [ ] §10: preflight, failure-ratio exit, stderr errors, failure hook (`OnFailure=` or Mac wrapper), dead-man ping

## 9. Monitor the monitor
The watchdog is itself monitored (journald scrape, heartbeat-file mtime check, or external Healthchecks.io ping); no log write in 2× its interval → alert on a secondary channel.

## 10. Fail loud — "exit 0" is not "it worked"
**Origin:** kb-scan-nightly (DAN-4336) ran 4.5 h with its embedding model missing; every duplicate check that needed it failed, it logged 14 ERROR lines to stdout, left stderr empty, would exit 0, and nothing alerted. Every check watched *liveness* (did it run, did it exit 0); none watched *correctness* (did it do its job). Design doc: `docs/architecture/silent-failure-prevention.md`.

**Fleet-wide:** a fix lands on every host in the fleet (every `machines/<host>/`; `machines/registry.sh` is a role lookup, not an inventory) with the same hook, never just the host where it broke; one host fixed is not a fix. Target architecture (central alert hub, central logs, allow-listed self-heal): the design doc §5.

Every unattended job (timer, cron, launchd agent, nightly batch) and every long-running service:
1. **Preflight before work.** Probe each hard dependency once, cheaply, before the first unit of work — model present (`/api/tags` or a 1-token embed), DB/queue reachable, API key valid, path writable. Any miss → one clear stderr line naming the dependency and the fix, then exit non-zero. Never spend hours on work a 1-second check would have refused.
2. **Count, don't swallow.** A caught exception inside the work loop increments a failure counter. At the end, failures above a threshold (default: any failure of a *core* dependency, or >10% of items) → exit non-zero with a summary line (`embed: 412/412 failed`). Degrading gracefully per item is fine; degrading silently for the whole run is not.
3. **Stop on a dead core dependency.** N consecutive failures of the same dependency (default 5) aborts the run instead of producing degraded output (articles without dedupe, rows without embeddings). Wrong output is worse than no output.
4. **Errors go to stderr; one log per job.** WARNING and above go to stderr (Python: a stderr handler at `WARNING`); progress may go to stdout. On the Mac, StandardOutPath/StandardErrorPath live under `~/Library/Logs/com.danizhaky/` (interim: the only directory `bin/log-error-scanner` reads until it covers every agent log path, design doc Stage 1b; until then it also misreads Eastern timestamps, so the failure hook in item 5 is the reliable signal, not the scanner). Timestamps carry a UTC offset (`%z`) so scanners never guess the timezone.
5. **A failure hook, always.** mfc1: `OnFailure=notify-failure@%n.service` (drop-in `10-onfailure.conf`; covered by `tests/test_mfc1_onfailure_coverage.py`). Long-running `Restart=` units get it too, plus `StartLimitBurst` (§3) so a crash loop ends in `failed`. systemd ≥254 documents `OnFailure=` firing on each crash under the default `RestartMode=normal`, but this is **unverified on mfc1**: prove it with a kill test before relying on it, and until then give every `Restart=` unit a `/health` probe or heartbeat. A clean exit 0 under `Restart=always` and a hung-but-alive process never trigger `OnFailure=` at all. Mac launchd has no OnFailure: wrap the job so a non-zero exit posts to `#infra-health`; until the shared wrapper ships (DAN-4336), post through `bin/slack-alert-infra-health.sh` (checks Slack's `ok`, retries, syslog fallback), never a home-made curl.
6. **Dead-man's switch for critical scheduled jobs** (the ~15 marked `critical` in the host's dependency manifest; the plan's check budget is capped). Other jobs rely on the failure hook plus their host's weekly drill. Ping Healthchecks.io at the end of a *successful* run — success means the job's own outcome check passed (e.g. a model-run job's result file says OK), not merely that the process exited 0 — and `/fail` otherwise; a missed ping alerts even if the host, the timer or the alert path is dead.
7. **`/health` checks what matters** (§4): a service whose core dependency is down returns non-200, not `{"status":"ok"}`.
8. **No `|| true` on the core call.** `|| true` is for optional, cosmetic steps only; mark each with a comment saying why its failure is harmless.
9. **Prove the failure path before Done.** A job is not Done until it has been made to fail once on purpose (missing dependency, forced non-zero) and the alert was seen in `#infra-health` (the fleet's standing alert sink; label test alerts `[DRILL]`). Testing only the happy path is how every gap in DAN-4336 shipped green.
10. **Declare dependencies where guu can see them.** A job's models, brew formulae and services belong in the host's dependency manifest so `guu` installs, updates and verifies them; a dependency only the job knows about is a dependency nobody keeps alive.

## 11. Agent service operations: what runs unattended (Dan, 2026-10-09, DAN-4250)
- **Restart/start is allowed.** An agent may run `systemctl --user restart` or `start` on a unit it owns after its config change has merged, with no approval. Verify the unit is `active` afterwards, or that its oneshot exited 0. This covers user units only. System units, `enable`/`disable`, unit-file edits outside a merged PR, and timer or cron schedule changes stay protected.
- **The auto-heal split.** An agent fixes a failure in its own service on its own when the fix is reversible: restart the unit, or roll back to the last merged config. It posts what it did in the alert thread and opens a Linear issue for the root cause. Anything that touches data (delete, migrate, restore), credentials, money or external sends pages Dan instead. One auto-heal attempt per incident: a second failure after the fix pages Dan.

## 12. What still needs Dan — the HUMAN inventory (DAN-4250, answers 2026-10-09)
The complement of §11: the five input points that stay with Dan by design. Agents route around them; nobody volunteers to absorb them.
- **Batched decisions owed to Dan** — the `Waiting:*` queue itself. Minimized as one decision card per topic with a staged recommendation, so one answer clears the batch; never one question per step.
- **1Password desktop unlock on a Mac** — `op inject` there needs the app unlocked, a device-only gate no agent can pass. Minimized by keeping secret-dependent unattended work on mfc1 (service account, no unlock); Mac injects run batched while Dan is at the keyboard.
- **Credential rotation** — protected; each one is confirmed with the exact target named. Minimized by pre-staging every rotation as a Blocked + `Waiting:Dan` issue whose steps Dan runs in one pass (e.g. DAN-4371).
- **Mac device gates** — SSO/MFA, OS dialogs, anything reachable only from a Mac desktop. Minimized API-first through the unified gateway, then Polar for browser flows, then batched into one session (e.g. DAN-4299).
- **Protected-action approvals** — deletion, overwriting user content, force-push, spending, external sends. Already the minimal form (one AskUserQuestion menu); automating this weakens the guardrail instead of reducing input.

One-time Dan device step (POLICY row 1, answered "Remember approvals"): set the 1Password SSH agent approval prompt to "once per app unlock" — 1Password desktop → Settings → Developer → SSH agent — on the MacBook Pro and the MacBook Air. Ends the per-use approval stalls from 2026-10-04; no mfc1 effect.
