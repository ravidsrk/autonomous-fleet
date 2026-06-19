# Runtime goal binding

How autonomous-fleet binds **native host goal/loop APIs** to **file-ledger truth**. Read with
`engine.md` when coordinating; adapters implement the mapping.

## Dual truth model

| Layer | Role | Survives compaction? |
|-------|------|----------------------|
| **File ledger + readiness + fleet-outcome** | Authoritative completion | Yes |
| **Native goal (`/goal`, `update_goal`, Stop hook)** | Turn continuation harness | Session-scoped |

Never call `GOAL_COMPLETE` until ledger gates and readiness validation pass. Native goals prevent
the coordinator from ending turns early; files prevent false completion.

## Primitives (9–12)

Optional when the host has no goal API (Orca uses ledger loop only).

| # | Primitive | Purpose |
|---|-----------|---------|
| 9 | `SET_GOAL(condition)` | Bind runtime goal to mission/campaign DONE (paraphrase ledger gates) |
| 10 | `UPDATE_GOAL(message)` | Progress ping; does not complete |
| 11 | `GOAL_COMPLETE(summary)` | End goal mode **after** file validation |
| 12 | `GOAL_BLOCKED(reason)` | Maps to `fleet-outcome.status: blocked` |

Record the active condition in the ledger under `## Runtime goal` (see templates below).

## Goal scopes

| Scope | Set by | Condition source | Clears when |
|-------|--------|------------------|-------------|
| **Campaign** | `fleet-program` | `PHASE: DONE` + all nodes DONE/SKIPPED | Program ledger terminal |
| **Mission** | Mission coordinator | Mission DONE + readiness | `fleet-outcome.status: done` |
| **Task unit** | Worker (optional) | Per-task acceptance in dispatch | Ledger task row flags true |

One campaign or mission goal per session. Swap at campaign node boundaries.

## Validation before GOAL_COMPLETE

Run these checks in order; any failure → keep working, do not complete:

1. Re-read mission/program ledger — all non-terminal tasks resolved.
2. Readiness doc exists with valid `fleet-outcome` YAML.
3. `./scripts/validate-fleet-outcome.sh` passes on readiness doc (when script available).
4. For campaigns: `PHASE: DONE` written in `docs/fleet-program-progress.md`.

## Ledger section template

Add to mission or program ledger after planning:

```markdown
## Runtime goal

SCOPE: <campaign | mission | task>
CONDITION: |
  <one-line paraphrase of DONE — must reference docs/ paths>
HOST: <grok | claude-code | codex | orca-ledger-only>
SET_AT: <ISO timestamp>
LAST_UPDATE: <progress message>
```

## Condition templates

### Campaign

```
Campaign <id> DONE: docs/fleet-program-progress.md PHASE is DONE,
every node in Node status is DONE or SKIPPED,
each readiness doc has valid fleet-outcome YAML,
./scripts/validate-fleet-outcome.sh passes on every readiness doc.
```

### Mission (substitute mission id, ledger, readiness, metrics)

```
Mission <mission-id> DONE: docs/<mission>-progress.md shows all mission task flags true,
docs/<mission>-readiness.md exists with fleet-outcome.status done and mission metrics satisfied,
all PRs merged into BASE, validate-fleet-outcome.sh passes.
```

### Task unit (worker dispatch footer)

```
Sub-goal: Task <task-id> done when ledger row <task-id> has MERGED=true and PR number recorded.
```

## Adapter binding

| Primitive | Grok | Claude Code | Codex | Orca |
|-----------|------|-------------|-------|------|
| `SET_GOAL` | `/goal <condition>`; record in ledger | `/goal <condition>` (v2.1.139+) | `/goal` in composer; enable `features.goals` | Ledger `## Runtime goal` only; `check --wait` loop |
| `UPDATE_GOAL` | `update_goal(message: "...")` | Automatic status; log in ledger | Goal progress UI; log in ledger | Ledger heartbeat line |
| `GOAL_COMPLETE` | `update_goal(completed: true, message)` after file check | Condition met or `/goal clear` after validation | Mark done in goal UI after validation | `PHASE: DONE` in ledger |
| `GOAL_BLOCKED` | `update_goal(blocked_reason: "...")` | `/goal clear` + blocked report | Pause goal | `escalation` message |
| `LOOP_POLL` | `/loop` or `scheduler_create` | `/loop` | Codex automations | External cron + terminal send |

## Plan mode pairing

| Fleet phase | Native |
|-------------|--------|
| Ambiguous campaign scope | `/plan` → user approval |
| Mission T-AUDIT / freeze | Coordinator explores; freezes artifact |
| Execution | `SET_GOAL` → iterate until ledger matches |

Plan produces frozen inputs; goal drives execution.

## Ralph / bounded loops (task units only)

Use `/ralph-loop` (Claude) or worker relaunch for **single bounded units** — not full missions.
Full missions need PR pipeline, placement, and review gates from the core.

## Headless unattended runs

Use `scripts/run-mission-headless.sh` for CI:

```bash
./scripts/run-mission-headless.sh grok doc-sync --max-turns 50
./scripts/run-mission-headless.sh claude fleet-program --max-turns 80
```

Pass a handoff file (`docs/<mission>-handoff.md`) or let the script generate a minimal prompt
from the mission skill name.

## Non-goals

- Replacing file ledgers with runtime goal state
- `GOAL_COMPLETE` on model self-assessment without file proof
- Parallel missions on one repo
- Campaign sequencing via `/loop` cron (use `fleet-program` coordinator)