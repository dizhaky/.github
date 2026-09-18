# Workflow: Continuous improvement

**When:** Any Project; default mode for Dan.  
**Result:** Problems found, fixed, verified, **shipped** — Dan sees outcomes, not homework.

## Loop

1. **Orient** — Project context, `notes.md`, gotchas, **Linear (this Project’s label/project)**, GitHub/vault as needed.
2. **Detect** — Linear open items for this Cursor Project, CI, health/auth gaps, flaky tests, stale docs, review findings, toil.
3. **Decide** — Take the recommended fix path yourself. Escalate only hard stops.
4. **Fix** — Surgical PR; no drive-by rewrites.
5. **Verify** — Real service checks; evidence in PR.
6. **Ship** — PR open/updated, checks green, merge if ungated. Non-negotiable end of run.
7. **Hand back** — Plain-language result + PR link; refresh `notes.md`.
8. **Park** — Extra ideas as `notes.md`/Linear items, not chat walls.

## Auth / keys

- **UNIFIED Gateway** is the access path for Linear, Google/Gmail, Microsoft Contacts, Slack, Notion, QBO, etc. — no side-door MCPs/personal tokens when UNIFIED can reach them.
- One production refresh holder; class-correct reconnect.
- Live health + next step > cached “creds present.”
- Never QBO-refresh from cloud/laptop agents.

## New Project bootstrap

1. Pull chats + vault + GitHub (+ Linear) → `docs/project-context.md`.
2. Seed `notes.md`.
3. Start the loop; don't wait for pasted context.

## Done

- [ ] Shipped PR this run (or one explicit ship-blocker)
- [ ] Verify evidence
- [ ] `notes.md` matches reality
- [ ] Dan only left with real hard-stop decisions

## Linear tie-out (required)

- **Scan:** On Project start and each improvement loop, query Linear for open issues tied to this Cursor Project; triage and resolve or park with a blocker.
- **Identity:** Use one stable key shared both sides — prefer Linear **project** or **label** = exact Cursor Project name (e.g. `UNIFIED Gateway`). Put that key on every issue you create from the Project.
- **Provenance:** Issue description/footer should include `Cursor Project: <name>` so Linear alone shows origin.
- **Create:** New work discovered in a Project → open/update Linear under that project/label; don’t leave orphan chat-only tasks.
- **Close the loop:** When shipped, mark Linear done with PR link; don’t leave Linear stale after merge.

## Coverage bar (≥95%)
Before ship: measure coverage on touched packages/paths; require **≥95%**. If under, add tests first. Waiver only from Dan with why + follow-up tracked in Linear under the Cursor Project key.

## Bot review sweep (auto-fix)

On every PR before merge (and when sweeping a Project):

1. List review comments/checks from **Claude Code, Codex, Bugbot, Greptile**, Cursor agents, and similar.
2. Triage: actionable + correct → fix on the PR branch immediately; wrong/noise → reply or dismiss with one-line why.
3. Push fixes; confirm CI still green (≥95% coverage bar still applies).
4. Don’t leave bot threads for Dan unless it’s a hard-stop product decision.

GitHub access: UNIFIED Gateway when available.

## Shared vault ↔ Cursor refresh

- **Write path for every harness:** notable work goes into the Obsidian vault (decisions, auth/custody, incidents, ship notes).
- **Read path for Cursor Projects:** on orient / each loop / after known external-agent activity, pull vault updates into `docs/project-context.md` (and `notes.md` status) so this Project stays current.
- Cadence: at least every Project session start; more often when Anti-Gravity/Codex/others are active on the same repo.
