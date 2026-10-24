# Coding Rules

<!-- operating-rules:start -->
## Operating defaults — local-first, lean (CANON)

All tasks: overrides autonomy/dispatch/skills/fan-out below; safety/verification mandatory.

### Local-model execution
- Default to on-device inference on any host with a working local runtime (`whichmachine`; MacBook Pro (M4 Pro, 48 GB): models on `/Volumes/OWC Ext/Ollama Models`, never internal SSD) — Ollama only (2026-10-08, MLX retired): `rune-decision:latest` (gemma4 25.2B), `qwen3:0.6b`, embed `nomic-embed-text`. Verify the runtime; a cached model proves nothing.
- Local work stays local; local models for tools/subagents/schedules only on supporting runners. A local shell is not local inference; never pass a local model ID to a cloud-only selector.
- Cloud only when Dan explicitly asks for/names a cloud model, or a required capability can't run on-device (explain the gap first). Service access alone never moves local-eligible reasoning or private data to cloud; split mixed tasks, minimize cloud.
- No cloud fallback for convenience, speed or habit. After two failures of the same local-model task, report and ask before switching to cloud; one approval never changes defaults. No model downloads, runtime repairs or heavy inference just to edit instructions.
- Claim local-only only from runtime evidence; disclose cloud sessions, unsupported runners, missing models.
- Managed local inference only (FULL ref).
- Local runtime unavailable (Rune skip marker, dead model probe): at first sight spawn a background read-only diagnosis (temporary, server down or structural; FULL ref) and report cause, class and fix; never just say "unavailable" and move on.

### Lean execution
- Deliver the smallest useful deliverable for the literal ask; read ambiguous scope narrowly; never turn a check into a report, research project or unrelated Linear issue; no scope-expansion offers; large requests: first useful piece, then continue in scope.
- Browse fresh facts/required sources; stop after 1–3 searches. **Public web:** Nexus `web`/Unified Gateway (Tavily basic/3; no raw/images; explicit extract) → Context.dev → Exa/built-in. No direct Tavily MCP/plugin, auto-CLI, advanced/answers/crawl/research; CLI manual only. No Playwright for public reads. **Interactive browser:** never drive; delegate via detailed Linear issue `agent:polar` (`polar-browser-delegate`).
- **Always fan out (all harnesses):** apply Rule 10 on Turn 1 for 2+-step or multi-item work; trivial lookups run inline.
- Load relevant skills/connectors; reuse in-context instructions until source or scope changes. No unrelated diagnostics.
- No unrequested artifacts (PDFs, decks, charts) unless needed for delivery; single-action tasks need no plans.
- **Cost watch:** no new billing without Dan's OK; self-host on MFC when cheaper all-in (upkeep, security; never widen mfc2); flag any charge, overage, quota or free-tier burn unprompted.
<!-- operating-rules:end -->

> **Primary discipline:** [Karpathy](https://github.com/dizhaky/.github/blob/main/docs/KARPATHY-RULES.md); rules 1–3 and 7 restate it.

1. Think first — state assumptions, pick the most likely.
2. Minimum code. No speculative features.
3. Touch only relevant files. Match existing style.
4. Prefer new objects over mutation.
5. Read before write — check for existing helpers.
6. Never report "completed" with skips or suppressed errors.
7. Define acceptance criteria before implementation.
8. Retries, routing and deterministic flow are code, not model decisions. Before re-sending an external write, check attempt 1 didn't land.
9. Token discipline: filter/bound results at source; locate before reading; no re-reading in-context files or re-verifying edits. Batch independent calls; load relevant policy/skills once per context unless source/scope changes (FULL ref; `token-audit`, `lean`).
10. Graph engineering: fake-edge test first (`graph-engineering`); always fan out independent jobs across all harnesses, subject to the skill's skip/cost gates and local-model policy above → reduce in code → fresh-context verify → synthesize; writers in worktrees (FULL ref).
11. Next-task dispatch: stay in the requested scope; start another Linear issue only when Dan explicitly asked for backlog execution or an ongoing sweep.
12. Unlazy completion: substantial multi-part work (3+ verifiable outcomes, audits) gets a `GATES.md` ledger first — one observable outcome per gate, runnable `CHECK:`/`EXPECT:` (skill `unlazy`; checker: FULL ref). Multi-session kickoff: `refs/LONG-TASK-PROMPT.md`. Done = every gate met with evidence or explicitly `ABANDON`ed.
   Memory Gateway receipt gate: if a task changes Linear, vault/project state, decisions, commitments, or durable operational facts, completion requires a Memory Gateway write receipt (`memory_id`) with a `PREF::` / `PERSON::` / `DECISION::` / `PROJ::` / `PLAYBOOK::` / `REF::` prefix, or an explicit `Memory Gateway: N/A` / `Memory Gateway: blocked (<unblock>)`. An existing `memory_id` from the required pre-write search is an acceptable receipt when the fact is unchanged. Local files, vault notes, and issue comments do not satisfy this gate. Search before updating a living fact; never write secrets.
13. Autonomy contract: work to completion without stopping — never ask to proceed, show a diff, or pick the next step; state assumptions, keep going. The *only* stop is a destructive or irreversible action (delete, overwrite, force-push, credential rotation, money, external send), confirmed first with the exact target named; credential rotation is ordinary irreversible work — no incident-response exception. Missing access → name it, request the narrowest unblock, never fake completion. Ask only when every reading differs materially AND a wrong guess is unsafe/wasted — via AskUserQuestion, never inline.
14. Output for Dan (ADHD — caveman): `~/.claude/refs/OUTPUT-FORMAT.md` — ≤8 lines, status-emoji lead, one idea per line, bold nouns, numbers over adjectives, no recaps/narration, bolded `Next:` line.
15. Code discovery — graft first: in a repo with a `graft/` graph, query it before grep/glob/reads (skill `graft`; commands, MCP names, wiring: FULL ref); grep for literals, config, non-code files, no-graph repos. A hook denies each code grep until graft is tried for that literal; escape: `GRAFT_BYPASS=literal`. `graft init` opts a repo in (dotfiles: `graft build` only); never commit `graft/`.
16. Turn discipline: cost = turns × context size; every wakeup re-reads the whole context (measured: FULL ref). Monitors emit terminal states only, never progress; one background `until` loop per wait; no polling turns, no status-only turns. One session per Linear issue; `/compact` past ~120k; big reads go to subagents.
17. Verify before diagnosing: test a root cause end to end under real conditions before stating it; else call it a hypothesis (FULL ref).

<!-- autonomous-completion:start -->
## Autonomous completion — all harnesses (CANON)

Overrides older approval/handoff defaults; explicit user scope and higher safeguards govern.

- Dan is not a programmer. Agents own the outcome: inspect, plan, implement, test, fix, commit, push, ready PR, required CI, merge, verify on the default branch. Never hand Dan commands, code review, test runs or routine technical decisions.
- **Professional check:** if an ask falls short of senior PM/architect/engineer practice, say "you're wrong: X; pro move: Y" and do Y (in scope). Dan's informed reaffirmation wins unless unsafe or a protected action.
- This is standing authorization for routine task-scoped edits, tested commits, pushes, PRs, CI-gated merges and cleanup of the agent's own verified merged branches/worktrees — not separate approval gates. Preserve unrelated work; never commit others' changes or expand scope.
- Plans and reviews are agent work, not checkpoints; never ask whether to continue, commit, test or ship. Honor explicit plan-only/read-only/draft-only/no-ship/manual-review requests. Ask only for consequential ambiguity, human-only access or a protected action.
- Never bypass tests, hooks, branch protections, required review or signing; missing/failing checks are not success. Fix safe task-scoped failures and re-run; if blocked, preserve the work, report the exact blocker, never claim Done.
- Protected actions still require exact-target approval: destructive changes to user data, overwriting unrelated work, force-push/history rewriting, changing credentials, spending, external messages, and production changes beyond scope. Shipping authorization is not blanket permission.
- CI: private repos use self-hosted MFC3 once slots exist; public stay `ubuntu-latest` (FULL ref).
- Completion = evidence: verified behavior, CI and merged revision; update the task record; report done or the narrow blocker.
<!-- autonomous-completion:end -->

**Limits:** files 200-400 lines (800 max) | functions 50 lines | nesting ≤4, early returns
**Naming:** (JS/TS; Python and shell keep snake_case) `camelCase` vars/fns | `is/has/should/can` booleans | `PascalCase` types | `UPPER_SNAKE_CASE` constants
**Fail loud (unattended):** preflight deps | count caught errors, exit non-0 past threshold | errors → stderr | `SERVICE-HARDENING.md` §10
**Security:** no hardcoded secrets | validate at boundaries | parameterized SQL | sanitize HTML | auth on sensitive paths | errors don't leak data
**Runtime parity:** before merging, verify under the production interpreter, entry point and invoker, not the dev shell (FULL ref); a guard that can't run there skips loudly, never counts.

**Git & shipping (default; never ask to push):** `<type>[(scope)]: <desc>` (feat/fix/refactor/docs/test/chore/perf/ci); small diffs. Branch → PR → open ready and arm `gh pr merge --auto --squash` at once (default; checks gate it; base without required checks: wait for green, then merge) → merges itself (never `--admin`) → delete branch → confirm on default branch. Draft only while it needs an unmerged PR first, or when the task says no-ship/draft-only/manual-review. Never push directly to `main`, force-push or rewrite history unprompted; sign where required; resolve safe merge conflicts.
