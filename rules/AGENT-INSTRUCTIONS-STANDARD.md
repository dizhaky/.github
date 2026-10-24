# Agent Instructions Standard

One rule set for every harness and every repo (DAN-4392). Each fact has one home; everything else imports or points to it. Enforced by `bin/agent-rules-lint`.

## Three layers

| Layer | Lives in | Holds | Loaded by |
|---|---|---|---|
| 1. Global | dotfiles `rules/` only (`CODING-RULES.md`, `LINEAR-WORKFLOW.md`, `KARPATHY-RULES.md`, …), plus the two hand-written harness globals: `.claude/CLAUDE.md` (Claude Code) and `codex/AGENTS.md` (Codex) | Policy that applies everywhere | `rules/generate-rules.sh` renders the per-harness globals; `install.sh` links them (`~/.claude/`, `~/.codex/AGENTS.md`, `~/AGENTS.md`, `~/.gemini/`, `~/.grok/`, Cursor) |
| 2. Repo | Root `AGENTS.md` + `CLAUDE.md` that is exactly `@AGENTS.md` | Repo deltas only: stack, commands, layout, CI, gotchas, test-pinned strings, repo-specific overrides of a global default | Every harness that reads `AGENTS.md`; Claude Code through the shim |
| 3. Folder (optional) | `AGENTS.md` + the same shim, in a subfolder | Only rules genuinely distinct from the repo's (vault `Projects/**` workstreams that mirror a claude.ai Project) | Harnesses walking from the repo root to the working dir |

Rules for layers 2 and 3:

- `CLAUDE.md` is a pure shim: optional YAML front matter (vault audit trail), the line `@AGENTS.md`, optional HTML comments. No headings, no "Claude Code notes". A Claude-only fact still goes in `AGENTS.md`; other harnesses ignore what does not apply to them.
- Never restate a global rule. Point to it (`rules/CODING-RULES.md` § …) or state only the repo's override.
- A test that pins a string in agent instructions reads `AGENTS.md`, never `CLAUDE.md`.
- Root `AGENTS.md` stays at or under 200 lines and 16 KiB, generated blocks excluded.
- No dated session logs ("Last session", PR/SHA lists); those go to `docs/system-log/`.
- No `.claude/CLAUDE.md` inside a repo: it is a second Claude-only file. Use the root pair.

## Generated blocks

Two fenced blocks in a repo `AGENTS.md` are generated, never hand-edited, and excluded from size and duplication checks:

- `<!-- graft:start -->` … `<!-- graft:end -->`: graft's own repo template, written by graft.
- `<!-- fleet-essentials:start … -->` … `<!-- fleet-essentials:end -->`: the cloud-session minimum. Cloud and web sessions load only the repo, so every repo carries it. The one source is `rules/CLOUD-ESSENTIALS.md`; `agent-rules-lint --fix <repo>` writes it (replacing a hand-written "Fleet essentials" section, or inserting before the first level-2 heading). Change the source, then run `--fix` across the fleet and ship one PR per repo.

## The lint

`bin/agent-rules-lint` checks one repo (default: the current git root), several paths, or the fleet (`--fleet`, every repo under `~/Dev` minus `bin/agent-rules-lint.skip`). Checks: `agents`, `claude` (pure shim), `nested` (folder pairs), `size`, `dated`, `fence` (present and byte-equal to the source) and `dup` (a CODING-RULES anchor pasted verbatim, or a paragraph whose 5-word shingles are mostly contained in one paragraph of a global source).

- **guu:** runs `--fleet --warn` at the end of every run (report only).
- **CI:** private repos run the composite action `dizhaky/.github/.github/actions/agent-rules-lint` (hosted in this hub so GHA does not need the private GH leftover; the runner downloads the hub at the pinned commit, so lint and `rules/` sources match). Not a required context. Public repos run the lint locally only. Callers must (a) pin the action and `actions/checkout` to a full 40-char commit SHA, never a branch or tag, and (b) never run fork PR code on the self-hosted runners: `pull_request` only (never `pull_request_target`), a same-repo `if:` gate, `permissions: contents: read`, `persist-credentials: false`. Caller job (bump the hub SHA deliberately when the standard or lint changes; see `docs/agent-rules-lint-host.md`):

```yaml
permissions:
  contents: read
jobs:
  agent-rules:
    if: github.event_name == 'push' || github.event.pull_request.head.repo.full_name == github.repository
    runs-on: [self-hosted, linux, x64, hetzner]
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@<40-char SHA> # v7
        with:
          persist-credentials: false
      - uses: dizhaky/.github/.github/actions/agent-rules-lint@40a05d9f2362b7e4621e83d789a7f563c262a8c6
```
- **Per-repo exceptions:** a `.agent-rules-ignore` file at the repo root lists nested paths (glob or dir prefix) the `nested` check skips, each with a `#` reason. Use it for global sources and archives, never to hide a fat shim.

## Exemptions

Forks and third-party checkouts keep upstream instruction files: `Agent-Reach`, `everything-claude-code`, `Graft`, `graft-upstream`. `agentmemory` (fork) gets only our `CLAUDE.md` shim. Archived repos are read-only. All are listed in `bin/agent-rules-lint.skip`.

## dotfiles itself

dotfiles follows layer 2 like any repo: root `AGENTS.md` holds dotfiles deltas, `CLAUDE.md` is the shim. The Codex global lives at `codex/AGENTS.md` so Codex sessions in dotfiles no longer load the global twice and other repos no longer inherit dotfiles' graft block. `~/CLAUDE.md` must not link to the repo `CLAUDE.md` (`install.sh` removes a stale link).
