---
name: fleet-program
description: >-
  Orchestrate autonomous-fleet missions on one repo — sequential chains and conditional
  campaign DAGs with if-outcome edges. Reads fleet-outcome YAML from each mission's readiness
  doc to branch (e.g. audit then tests if no P0s, else dependency-update). One mission active
  at a time per repo; cross-repo parallel via separate sessions. Does not run parallel missions
  on the same repo. Use for "repo health program", "audit then test", "docs then bugs if
  needed", mission chains, fleet campaign. Install from github.com/ravidsrk/autonomous-fleet.
  Trigger on: "fleet program", "fleet campaign", "mission chain", "if P0 then", "repo health",
  "conditional fleet run".
license: MIT
compatibility: Requires git and gh CLI; install mission skills via npx skills
metadata:
  author: "ravidsrk"
  version: "1.1.0"
  fleet-component: "program"
---

# fleet-program

Meta-skill for **mission-level orchestration**: linear programs and **conditional campaign DAGs**.
You are the PROGRAM COORDINATOR — the engine, one level up for missions. Same discipline: file
ledger, frozen outcomes, no-stop autonomy, one active mission per repo.

## Required skills

1. `autonomous-fleet-core` — `references/engine.md`, `references/composition.md`,
   `references/fleet-outcome.md`
2. One runtime adapter: `autonomous-fleet-adapter-orca`, `autonomous-fleet-adapter-claude-code`,
   or `autonomous-fleet-adapter-grok`

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

## Handoff notes
```

Status per node: `PENDING` | `RUNNING` | `DONE` | `SKIPPED`.

## Choose mode

| Mode | When | Spec |
|------|------|------|
| **linear** | Ordered list, no branches | [programs.md](references/programs.md) table → implicit `always` edges |
| **campaign** | `if` branches on outcomes | [campaigns.md](references/campaigns.md) DAG YAML |
| **parallel_repos** | Same mission on different repos | campaigns.md `parallel_repos` — **separate sessions**, aggregate at end |

Default vague intent → `repo-health` campaign (linear DAG).

## Planning

1. **SELF-ORIENT** (core engine).
2. Parse user request → linear queue OR campaign YAML OR `parallel_repos`.
3. Write spec + ledger; record in DECISIONS.md.
4. **BASE:** `<BRANCH_PREFIX><campaign-id>-base` off default branch at HEAD (first node).

## Per-mission loop (single repo)

1. Set `CURRENT_NODE`, `ACTIVE_MISSION`, `PHASE: NODE-<id>`.
2. Activate **only** that mission skill.
3. Run mission to DONE (mission ledger + readiness with **`fleet-outcome` YAML**).
4. **Parse outcome:** read YAML frontmatter from readiness doc per
   [fleet-outcome.md](../autonomous-fleet-core/references/fleet-outcome.md). Store in **Last
   fleet-outcome**. If missing, extract metrics from readiness prose and log a warning in
   DECISIONS.md.
5. Mark node `DONE`; update handoff (deferrals → next mission discovery tasks).
6. **Pick next node:**
   - **Linear:** next row in queue.
   - **Campaign:** from `edges[current_node]`, evaluate each `if` **in order**; first true edge
     wins. Expressions use `fleet-outcome.metrics.*`, top-level fields, and `always`. See
     [campaigns.md](references/campaigns.md).
   - No matching edge → `PHASE: DONE`.
7. If `fleet-outcome.status == blocked` → `PHASE: BLOCKED`; record; stop chain unless mission
   rules allow retry.

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