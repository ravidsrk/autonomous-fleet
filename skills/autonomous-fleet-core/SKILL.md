---
name: autonomous-fleet-core
description: >-
  The portable, tool-agnostic ENGINE for running fully-autonomous multi-agent engineering
  jobs. Shipped mission skills (doc-sync, test-coverage, adversarial-review-and-fix) invoke
  THIS engine plus exactly one ADAPTER (orca, claude-code, grok, or another runtime). Eighteen
  additional missions are documented under docs/exploratory/missions/ and re-promote on
  real-run evidence. This core holds
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
  version: "1.2.3"
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

For review missions emitting structured findings (`adversarial-review-and-fix` and any future
reviewer phase), see [references/review-findings.md](references/review-findings.md): the
JSON schema, the source-verification CLI, the fix-strategy/confidence gating rules. For RUNTIME
enforcement of the engine's EVID/WT_CLEAN/e2e_verified disciplines via a Claude Code Stop hook,
see [references/strict-mode.md](references/strict-mode.md): opt-in install of the stop-verify
gate that refuses session termination without verifiable evidence on disk.

Every run that emits first-class artifacts (findings, blind-fix files, verifier summaries) leaves a
manifest-audited trail under `.fleet/runs/<run_id>/`. See
[references/run-archive.md](references/run-archive.md) for the manifest scheme and the
`archive_enabled` gate (a `status: done` outcome is rejected if its archive doesn't validate).

**Substrate distribution (skills-install mode).** The Python enforcement substrate (the
validators above plus `lib/`) ships WITH this skill under
[`assets/substrate/`](assets/substrate/) — on a skills-installed repo it lives at
`.agents/skills/autonomous-fleet-core/assets/substrate/` and each CLI runs standalone with
`python3` (deps: `assets/substrate/requirements.txt`; version pinned in
`assets/substrate/substrate-manifest.json`). In a framework clone, prefer the canonical
`scripts/` copies. Shell wrappers (`preflight.sh`, `validate-fleet-outcome.sh`,
`run-sandboxed.sh`) remain clone-only for now. `setup-autonomous-fleet` records the resolved
`SUBSTRATE_PATH` in `docs/agents/fleet-config.md`.

Ports of Agent Orchestrator mechanisms (nudge dedup, stacked PR, hook-signal, review supersede)
without adopting AO's daemon: [references/ao-adoptions.md](references/ao-adoptions.md).

## Primitives (summary)

The active adapter must implement: `PLACE`, `SPAWN_WORKER`, `DISPATCH`, `WAIT`, `INSPECT`,
`WORKER_DONE` / `ASK` / `REPLY`, `OPEN_PR` / `MERGE_PR` / `CLEANUP`, `SYNC_TASK_STATE`.
When the host supports goal mode, also implement: `SET_GOAL`, `UPDATE_GOAL`, `GOAL_COMPLETE`,
`GOAL_BLOCKED`, and `LOOP_POLL` (host-native scheduler; Orca exempt — see `runtime-goals.md`).
Optional primitive 14, `CONTINUE_WORKER` (re-attach an existing resumable session for an in-flight
task), is implemented by adapters whose runtime exposes a restore command and ALIASED to
`SPAWN_WORKER` (idempotent relaunch) otherwise — see `engine.md`.
