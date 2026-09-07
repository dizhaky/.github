# Karpathy's Four Rules

Agent coding principles for LLM-assisted development. Canonical Cursor rule: [`karpathy-four-rules.mdc`](../.cursor/rules/karpathy-four-rules.mdc). Repo template: [`.github/repo-templates/cursor-rules-karpathy.mdc`](../.github/repo-templates/cursor-rules-karpathy.mdc).

Derived from Andrej Karpathy's Jan 2026 field notes on LLM coding agents. Biases toward care in what gets written — think first, keep it minimal, edit surgically, verify — never toward pausing the work; rule 1 settles uncertainty and you keep going.

| # | Rule | One-liner |
|---|------|-----------|
| 1 | **Think Before Coding** | State assumptions and proceed on the most likely; don't stop to ask. |
| 2 | **Simplicity First** | Minimum code that solves the problem — nothing speculative. |
| 3 | **Surgical Changes** | Touch only what you must; every changed line traces to the request. |
| 4 | **Goal-Driven Execution** | Define success criteria and verify before calling work done. |

## Full rules

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

- State assumptions out loud and proceed on the most likely one; don't pick interpretations silently, and don't stop to ask.
- Where readings differ, say which one you took and why, then keep going. Ask only when every reading leads to materially different work *and* proceeding on the wrong one would be unsafe or waste the work.
- Push back when warranted — in the work, as a stated objection you then act past, not as a question that halts it.
- The only stop is a destructive or irreversible action — delete, overwrite, force-push, money, external send — which gets confirmed first with the exact target named. Rotating an already-exposed secret is the exception: it is compromised the moment it leaks, so it goes immediately without confirmation.

### 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No unrequested features, abstractions, flexibility, or error handling for impossible cases.
- If 200 lines could be 50, rewrite.

### 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

- Don't improve adjacent code, comments, or formatting. Match existing style.
- Remove orphans your changes created; don't delete pre-existing dead code unless asked.
- Every changed line should trace to the user's request.

### 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

- Transform imperative tasks into verifiable goals (e.g. "fix the bug" → write reproducing test, then pass it).
- For multi-step work, state a brief plan with verification at each step.

## Adopt in a repo

Copy or symlink into `.cursor/rules/`:

```bash
# From this repo after clone
cp .cursor/rules/karpathy-four-rules.mdc YOUR_REPO/.cursor/rules/
# Or use the repo template
cp path/to/dizhaky/.github/.github/repo-templates/cursor-rules-karpathy.mdc .cursor/rules/karpathy-four-rules.mdc
```

Set `alwaysApply: true` in frontmatter so Cursor applies the rule in every session.
