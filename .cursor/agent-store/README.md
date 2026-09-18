# Dan’s global agent Context

**Read first in every Project:** [preferences.md](preferences.md)

This user-scoped store is **global across all Cursor Projects** (not per-Project settings). It is the standing team charter:

| File | Role |
|---|---|
| [preferences.md](preferences.md) | Index — max autonomy, ship every run, hard stops only |
| [principles/autonomous-team.md](principles/autonomous-team.md) | PM+eng+QA posture; decide & execute |
| [workflows/continuous-improvement.md](workflows/continuous-improvement.md) | Detect → fix → verify → ship loop |

Canonical installable copy: **`dizhaky/dotfiles`** → `cursor/agent-store/` (always-on rule `cursor/rules/agent-store-prefs.mdc`; `./install.sh` + `cursor/bin/install-karpathy-repo-rules.sh`). If they drift, reconcile both.

Dan is not a coder: prefer action, take recommended options, explain in plain language, only escalate hard stops.

Projects must also **scan Linear** for their own open work and tag Linear items with the Cursor Project name so origin is obvious.

## Access path
Agents reach Linear, Google/Gmail, Microsoft Contacts, Slack, Notion, QBO, and other apps **through UNIFIED Gateway** (not side-door MCPs). See [preferences.md](preferences.md).

**Ship bar:** ≥95% automated test coverage on what we ship (see preferences).

**PRs:** auto-scan Codex/Bugbot/Greptile/Claude reviews and fix before merge.

Cross-harness (Anti-Gravity, Codex, etc.): write notables to the **vault**; Cursor Projects refresh from vault on a cadence.

## Install paths

| Location | Role |
|---|---|
| `/cursor/stores/user/` | Live Agent Store (global Context) — edit here first |
| `dizhaky/dotfiles` → `cursor/agent-store/` | Installable mirror + always-on rule `cursor/rules/agent-store-prefs.mdc` |
| `~/.cursor/agent-store/` | After `./install.sh` on macOS |
| `.cursor/agent-store/` in each repo | After `cursor/bin/install-karpathy-repo-rules.sh` |

If Agent Store and dotfiles drift, reconcile both.
