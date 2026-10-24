# agent-rules-lint composite host

Fleet CI used to resolve `dizhaky/dotfiles/.github/actions/agent-rules-lint@SHA`.
After Origin SoT for dotfiles, that private leftover must not be required for GHA.

This repo (hard-skip hub, stays on GitHub) now hosts a vendored copy of:
- `.github/actions/agent-rules-lint/action.yml`
- `bin/agent-rules-lint` (+ skip file)
- the `rules/` + harness instruction sources the lint reads for fence/dup checks

Callers should pin:

```yaml
- uses: dizhaky/.github/.github/actions/agent-rules-lint@<40-char SHA>
```

Bump the pin when Origin SoT updates the lint or CLOUD-ESSENTIALS; re-vendor from
`dan-izhaky/dotfiles` (or GH leftover while still reachable) then bump callers.
Source of truth for rule text remains Origin `dan-izhaky/dotfiles`; this tree is a
CI resolution host only (DAN-4942).
