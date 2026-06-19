---
name: fleet-program
description: >-
  Orchestrate autonomous-fleet missions on one repo — sequential chains and conditional
  campaign DAGs with if-outcome edges. Reads fleet-outcome YAML from each mission's readiness
  doc to branch (e.g. audit then tests if no P0s, else dependency-update). One mission active
  at a time per repo; cross-repo parallel via separate sessions. Does not run parallel missions
  on the same repo. Use for "repo health program", "audit then test", "docs then bugs if
  needed", mission chains, fleet campaign, ship with proof, align then ship, quality gate.
  Install from github.com/ravidsrk/autonomous-fleet.
  Trigger on: "fleet program", "fleet campaign", "mission chain", "if P0 then", "repo health",
  "conditional fleet run", "ship safely", "ship with proof", "finish stalled product",
  "align then ship", "production ready", "quality gate".
license: MIT
compatibility: Requires git and gh CLI; install mission skills via npx skills
metadata:
  author: "ravidsrk"
  version: "1.2.0"
  fleet-component: "program"
---

# fleet-program

Meta-skill for **mission-level orchestration**: linear programs and **conditional campaign DAGs**.
You are the PROGRAM COORDINATOR — the engine, one level up for missions. Same discipline: file
ledger, frozen outcomes, no-stop autonomy, one active mission per repo.

## Required skills

1. `autonomous-fleet-core` — `references/engine.md`, `references/composition.md`,
   `references/fleet-outcome.md`, `references/runtime-goals.md`
2. One runtime adapter: `autonomous-fleet-adapter-orca`, `autonomous-fleet-adapter-claude-code`,
   `autonomous-fleet-adapter-grok`, or `autonomous-fleet-adapter-codex`

Install missions via `npx skills add` before starting.

Load **only** the active mission's skill while that mission runs — never two mission skills at once.

## Optional skills

| Skill | Activate when | If unavailable |
|-------|---------------|----------------|
| `autonomous-fleet` | Vague intent; need catalog | Pick preset from [references/programs.md](references/programs.md) or [references/campaigns.md](references/campaigns.md) |

## Program ledger

`docs/fleet-program-progress.md`:

```markdown
# Fleet program progress

MODE: <linear | campaign | parallel_repos>
CAMPAIGN: <id>
PHASE: <PLANNING | NODE-<id> | DONE | BLOCKED>
ACTIVE_MISSION: <mission-id | none>
CURRENT_NODE: <node-id | none>
BASE: <branch>

## Campaign spec
(paste YAML from campaigns.md or user)

## Last fleet-outcome
(paste parsed summary from last readiness doc)

## Node status
| Node | Mission | Status | Readiness doc |
|------|---------|--------|---------------|

## Runtime goal

SCOPE: campaign
CONDITION: |
  Campaign <id> DONE: docs/fleet-program-progress.md PHASE is DONE,
  every node DONE or SKIPPED, each readiness doc has valid fleet-outcome YAML.
HOST: <adapter runtime>
SET_AT: <timestamp>
LAST_UPDATE: <progress>

## Handoff notes
```

Status per node: `PENDING` | `RUNNING` | `DONE` | `SKIPPED`.

## Choose mode

| Mode | When | Spec |
|------|------|------|
| **linear** | Ordered list, no branches | [programs.md](references/programs.md) table → implicit `always` edges |
| **campaign** | `if` branches on outcomes | [campaigns.md](references/campaigns.md) DAG YAML |
| **parallel_repos** | Same mission on different repos | campaigns.md `parallel_repos` — **separate sessions**, aggregate at end |

Default vague intent → `repo-health` campaign (linear DAG). Security / pre-merge →
`ship-with-proof` or `secure-ship`. Stalled product (explicit Tier 3) → `align-then-ship`.
Acceptance / readiness → `quality-gate`. Community hooks: [community-skills.md](../autonomous-fleet-core/references/community-skills.md).

## Planning

1. **SELF-ORIENT** (core engine).
2. Parse user request → linear queue OR campaign YAML OR `parallel_repos`.
3. Write spec + ledger; record in DECISIONS.md.
4. **BASE:** `<BRANCH_PREFIX><campaign-id>-base` off default branch at HEAD (first node).
5. **SET_GOAL** (campaign scope) per [runtime-goals.md](../autonomous-fleet-core/references/runtime-goals.md) —
   condition must reference `docs/fleet-program-progress.md` and readiness validation.

## Runtime goal binding

| Step | Action |
|------|--------|
| Campaign start | `SET_GOAL(campaign_done_condition)`; write `## Runtime goal` in program ledger |
| Each node start | `SET_GOAL(mission_done_condition)` — replaces campaign goal for this session |
| Node complete | `UPDATE_GOAL("node <id> done: <fleet-outcome summary>")`; run `validate-fleet-outcome.sh` |
| Campaign complete | `GOAL_COMPLETE` only when `PHASE: DONE` in file + all validations pass |
| Blocked node | `GOAL_BLOCKED` if `fleet-outcome.status == blocked` and no retry |

Mission goal template (substitute mission id, ledger, readiness, metrics):

```
Mission <mission-id> DONE: docs/<mission>-progress.md all task flags true,
docs/<mission>-readiness.md with fleet-outcome.status done,
all PRs merged into BASE, validate-fleet-outcome.sh passes.
```

Unattended CI: `./scripts/run-campaign.sh <grok|claude|codex> --preset repo-health --max-turns N`
(or `--campaign docs/<campaign>.yaml`; add `--dry-run` to plan only)

## Per-mission loop (single repo)

1. Set `CURRENT_NODE`, `ACTIVE_MISSION`, `PHASE: NODE-<id>`.
2. **SET_GOAL** for active mission (see template above).
3. Activate **only** that mission skill.
4. Run mission to DONE (mission ledger + readiness with **`fleet-outcome` YAML**).
5. **Parse outcome:** read YAML frontmatter from readiness doc per
   [fleet-outcome.md](../autonomous-fleet-core/references/fleet-outcome.md). Store in **Last
   fleet-outcome**. If missing, extract metrics from readiness prose and log a warning in
   DECISIONS.md.
6. **UPDATE_GOAL** with node summary; mark node `DONE`; update handoff (deferrals → next mission
   discovery tasks).
7. **Pick next node:**
   - **Linear:** next row in queue.
   - **Campaign:** from `edges[current_node]`, evaluate each `if` **in order**; first true edge
     wins. Expressions use `fleet-outcome.metrics.*`, top-level fields, and `always`. See
     [campaigns.md](references/campaigns.md).
   - No matching edge → `PHASE: DONE`.
8. If `fleet-outcome.status == blocked` → `PHASE: BLOCKED`; `GOAL_BLOCKED`; stop chain unless
   mission rules allow retry.
9. When no next node → set `PHASE: DONE`; **GOAL_COMPLETE** after file validation.

## Conditional expression evaluator

| `if` value | True when |
|------------|-----------|
| `always` | Always |
| `p0_open > 0` | `metrics.p0_open` compares (same for any metric key) |
| `p0_open == 0` | Equality |
| `code_bug_findings > 0` | From doc-sync metrics |
| `status == blocked` | Top-level status |
| `deferred_missions contains bug-batch` | Any deferral id matches |

Unknown expression → log in DECISIONS.md, skip edge (do not guess).

## Parallelism

| Case | Rule |
|------|------|
| Same repo, two missions | **Forbidden** — no shared lock manager |
| Tasks inside active mission | Mission hot-file + placement rules |
| Different repos | `parallel_repos`: one coordinator loop per repo OR user runs separate sessions |

## Autonomy (program level)

Same as core: do not stop between missions; do not ask "continue to next mission?"; circuit-breaker
on a node → `SKIPPED` + DECISIONS.md, then evaluate if campaign can proceed.

## DONE

All nodes `DONE` or `SKIPPED`, or `PHASE: DONE` / `BLOCKED` with reason. FINAL report: campaign
spec, per-node outcomes (fleet-outcome summaries), readiness links, combined deferrals.

## Safe defaults

- First-time repo: `repo-health` campaign.
- Security intent: `secure-ship` or `audit-branch` (conditional).
- Tier 3 missions only when user explicitly requests.