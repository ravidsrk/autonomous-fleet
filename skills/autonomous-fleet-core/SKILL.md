---
name: autonomous-fleet-core
description: >-
  The portable, tool-agnostic ENGINE for running fully-autonomous multi-agent engineering
  jobs. Mission skills (doc-sync, test-coverage, dependency-update, cleanup, bug-batch,
  adversarial-review-and-fix, targeted-migration, design-integration,
  landing-page-convergence, legacy-rebuild, take-product-to-completion) invoke THIS engine
  plus exactly one ADAPTER (orca, claude-code, grok, or another runtime). This core holds
  everything that does NOT depend on orchestration tool: self-orientation, fully-autonomous
  coordinator behaviour with file-ledger boolean gates, context-handoff to survive
  compaction, the worker-placement DECISION LOGIC (dependent vs independent), the
  PR-per-task pipeline with commits-preserved + conflict-aware merge + worktree cleanup, the
  empirical risk tiers, safety rails, secret hygiene, and commit/authorship policy. It
  speaks in PRIMITIVES; the ACTIVE ADAPTER maps each primitive to its tool's real commands.
  Load with a mission skill and one runtime adapter — do not run alone.
license: MIT
compatibility: Requires git and gh CLI in the target repository
metadata:
  author: "ravidsrk"
  version: "1.1.0"
  fleet-component: "core"
---
# Autonomous Fleet — Core Engine (tool-agnostic)

You are the COORDINATOR for an autonomous multi-agent run. You are a THIN LOOP-HOLDER: create
tasks, spawn workers, dispatch, wait, answer worker questions from defaults, sequence the
pipeline, decide what runs next and how parallel. You do NOT review, code, or merge yourself — all
dispatched. Context stays light; the source of truth is the ledger FILE, not your memory.

## Required composition

Do not run this skill alone. A **mission** skill defines the work; an **adapter** skill defines
runtime mechanics.

## Instructions

Read and follow [references/engine.md](references/engine.md) in full before coordinating any run.
It contains self-orientation, autonomy enforcement, worker placement, the PR pipeline, safety
rails, and all other engine rules.

For how missions, worker skills, optional skills, and campaigns compose, read
[references/composition.md](references/composition.md), [references/community-skills.md](references/community-skills.md),
[references/fleet-outcome.md](references/fleet-outcome.md), and [references/runtime-goals.md](references/runtime-goals.md)
for native `/goal` / `update_goal` binding. Per-repo defaults: `setup-autonomous-fleet` → `docs/agents/fleet-config.md`.
Mission chains and conditional DAGs use `fleet-program` — not a second mission loaded alongside
the first.

## Primitives (summary)

The active adapter must implement: `PLACE`, `SPAWN_WORKER`, `DISPATCH`, `WAIT`, `INSPECT`,
`WORKER_DONE` / `ASK` / `REPLY`, `OPEN_PR` / `MERGE_PR` / `CLEANUP`, `SYNC_TASK_STATE`.
When the host supports goal mode, also implement: `SET_GOAL`, `UPDATE_GOAL`, `GOAL_COMPLETE`,
`GOAL_BLOCKED` (Orca exempt — see `runtime-goals.md`).
