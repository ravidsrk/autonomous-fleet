---
name: fleet-program
description: >-
  Run an ordered chain of autonomous-fleet missions on one repo — one mission at a time, with
  handoffs via readiness docs and DECISIONS.md. Use when the user wants multiple missions in
  sequence ("make this repo healthy", "docs then tests then cleanup", "audit then fix then
  sync docs"), not a single mission. Loads autonomous-fleet-core plus one adapter; executes
  each mission skill to DONE before starting the next. Does not run missions in parallel on
  the same repo. Install from github.com/ravidsrk/autonomous-fleet. Trigger on: "fleet
  program", "run mission chain", "doc-sync then test-coverage", "repo health program",
  "sequential fleet missions".
license: MIT
compatibility: Requires git and gh CLI; install mission skills via npx skills
metadata:
  author: "ravidsrk"
  version: "1.0.0"
  fleet-component: "program"
---

# fleet-program

Meta-skill for **sequential multi-mission runs** on a single repository. You are the PROGRAM
COORDINATOR: pick or accept a mission chain, run each mission to completion, hand off state, then
start the next. You do not merge mission instructions — each mission runs as its own full run.

## Required skills

Before executing, activate:

1. `autonomous-fleet-core` — read `references/engine.md` and `references/composition.md`
2. One runtime adapter: `autonomous-fleet-adapter-orca`, `autonomous-fleet-adapter-claude-code`,
   or `autonomous-fleet-adapter-grok`

Install each mission in the program via `npx skills add` before starting (or `--skill '*'`).

Do **not** load multiple mission skills at once. Load **only** the active mission's skill while
that mission runs.

## Optional skills

| Skill | Activate when | If unavailable |
|-------|---------------|----------------|
| `autonomous-fleet` | User intent is vague; need mission catalog | Pick program from [references/programs.md](references/programs.md) |
| Mission-specific optionals | Active mission's `## Optional skills` table | Follow that mission's fallback column |

## Program ledger

`docs/fleet-program-progress.md`:

```markdown
# Fleet program progress

PROGRAM: <id>
PHASE: <PLANNING | MISSION-n | DONE>
ACTIVE_MISSION: <mission-id | none>

## Mission queue

| # | Mission | Status | BASE used | Readiness doc |
|---|---------|--------|-----------|---------------|
| 1 | doc-sync | PENDING | | |
| 2 | test-coverage | PENDING | | |

## Handoff notes

(carry deferrals from prior readiness docs into next mission's T-AUDIT/T-MAP)
```

Status values: `PENDING` | `RUNNING` | `DONE` | `SKIPPED` (with reasoning in DECISIONS.md).

## How to plan a program

1. **SELF-ORIENT** per core engine (REPO_ROOT, MAINTAINER, BRANCH_PREFIX, default branch).
2. Parse user intent or select a preset from [references/programs.md](references/programs.md).
3. Write the mission queue to the program ledger; record program id and rationale in
   `docs/DECISIONS.md`.
4. For each mission in order — **only one active at a time**:

### Per-mission loop

1. Set `ACTIVE_MISSION` and `PHASE: MISSION-n` in the program ledger.
2. Activate **only** that mission's skill (+ core + adapter already loaded).
3. **BASE branch:** first mission → new branch off default branch at HEAD
   (`<BRANCH_PREFIX><program-slug>-base` e.g. `fleet/repo-health-base`). Later missions → same
   BASE if prior mission's work merged there; if prior mission promoted to default branch, new
   BASE off updated default at HEAD (record in DECISIONS.md).
4. Run the mission to its DONE condition (mission ledger + readiness doc exist).
5. Read prior mission readiness **Recommended next missions** — if the queue already covers them,
   note in handoff; if user added ad-hoc missions, append to queue with reasoning.
6. Mark mission `DONE` in program ledger; copy readiness path and PR summary into handoff notes.
7. Proceed to next mission or `PHASE: DONE`.

## Conditional steps

| Condition | Action |
|-----------|--------|
| User named explicit chain | Use that order |
| User said "healthy repo" / similar | Default `repo-health` preset (programs.md) |
| Prior readiness recommends a mission not in queue | Append if user intent implies it; else record in FINAL report only |
| Mission HARD EXTERNAL DEPENDENCY blocks | Pause program at that mission; single allowed user gate per mission rules |
| Mission fails circuit-breaker 3× | Mark `SKIPPED`, record in DECISIONS.md; ask in FINAL report whether to continue chain |

## Parallelism

**Never** run two missions concurrently on the same repo. Within each mission, use that mission's
parallel task rules (independent placements, hot-file serialization).

## DONE (program)

All queued missions `DONE` or explicitly `SKIPPED`, `PHASE: DONE`, program ledger complete. Send
one FINAL report: per-mission summary, readiness doc links, combined **Recommended next missions**
from the last mission, any SKIPPED items.

## Safe defaults

- **First program on a repo:** `repo-health` (doc-sync → test-coverage → cleanup).
- **After audit:** `secure-ship` (adversarial-review-and-fix → dependency-update → doc-sync).
- Prefer Tier 1 missions early in a chain; Tier 3 only when user intent is explicit.