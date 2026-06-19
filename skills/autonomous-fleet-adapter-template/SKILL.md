---
name: autonomous-fleet-adapter-template
description: >-
  TEMPLATE for writing a new autonomous-fleet adapter (e.g. codex, gemini-cli, a custom CLI
  fleet, or a raw tmux+worktrees setup). Copy this, rename to
  autonomous-fleet-adapter-YOUR-TOOL, and fill in how YOUR runtime implements each PRIMITIVE
  the core calls. The missions and the core never change — only this mapping does. Use when
  adding a new orchestration runtime to autonomous-fleet. Not a runnable mission skill.
license: MIT
compatibility: Reference template for adapter authors; not a runnable mission
metadata:
  author: "ravidsrk"
  version: "1.0.0"
  fleet-component: "adapter-template"
  runnable: "false"
---


# Adapter TEMPLATE — how to support a new tool

`autonomous-fleet-core` is tool-agnostic: it calls a fixed set of PRIMITIVES and never hard-codes a
runtime's commands. To run the whole mission library on a new tool, you implement those primitives
once, here. Copy `skills/autonomous-fleet-adapter-template/` to
`skills/autonomous-fleet-adapter-<tool>/`, set frontmatter `name` to match the directory, and fill
each section below with your tool's real commands. Then any mission runs by loading the core +
your adapter.

Pick a `branch prefix` default for your tool. State your tool's CONCURRENCY MODEL (does it have a
persistent orchestration daemon like Orca, or is the coordinator itself a session like Claude
Code?) — that determines whether WAIT() is a real blocking call or ledger-polling, and whether the
file ledger is the sole source of truth or a daemon also holds state.

## PRECONDITIONS
List the exact start-up checks for your runtime (runtime reachable / auth / worktree support /
gitleaks / BASE exists).

## PRIMITIVE → <TOOL> MAPPING (fill every one)

### PLACE(kind)
- `independent` → <how your tool makes an isolated checkout on its own branch off BASE>.
- `dependent` → <how your tool runs a fresh worker in the current checkout/branch>.

### SPAWN_WORKER(role, placement) → handle in auto/max mode
<the command(s) to create a worker in the given placement, with the tool's auto/skip-permissions +
max-effort flags. Map roles (builder/reviewer/integrator) to specific agent CLIs. State what
"ready" means and how you wait for it before DISPATCH.>

### DISPATCH(task, handle)
<how a task spec is handed to a worker so it will report completion. If your tool injects a
preamble, say so; if not, how the worker learns the completion contract.>
**Required:** prepend mission `## Worker skills` for the worker's role (see core engine.md WORKER
SKILLS block) before the task spec in every dispatch/inject payload.

### WAIT(types, timeout)
<blocking call if the tool has a daemon; otherwise the polling strategy: re-read the file ledger +
check worker/git state. State that a timeout is a checkpoint, not failure, and that an active
worker is alive, not done.>

### INSPECT() — non-destructive
<commands to read task/worker/PR/ledger state WITHOUT consuming it.>

### WORKER_DONE / ASK / REPLY
<how a worker signals completion (carry the work identifiers + files modified + summary); how a
worker asks a blocking question and how the coordinator answers — or, if the tool can't block
cross-worker, how DECISION DEFAULTS + ledger-recorded BLOCKED items substitute, never escalating to
the user.>

### OPEN_PR / MERGE_PR(conflict-aware) / CLEANUP
<usually `gh` via your tool's shell. KEEP the conflict-aware rule verbatim: check mergeable, rebase
onto BASE, resolve, re-test green, re-review if logic changed, then merge with a MERGE COMMIT
(commits preserved, NEVER squash), delete branch, clean the checkout.>

### SYNC_TASK_STATE(task, status)
<how the tool's native task view is kept aligned with the file ledger — or a note that the ledger +
your tool's todo mechanism together are the task view.>

## DIAGNOSTICS
<how to diagnose a worker that finished without reporting; how the coordinator survives its own
context limit via the CONTEXT HANDOFF block in the ledger.>

## NON-NEGOTIABLES THAT DO NOT CHANGE PER TOOL
These come from the core and your adapter must NOT weaken them:
- One PR per unit, commits preserved, NEVER squash, authored by MAINTAINER, no agent/tool trailers.
- Conflict-aware merge (never force a merge over conflicts or a red suite).
- Checkout cleanup on every merge.
- Safety rails (testnet/staging/fixtures only; merge ≠ deploy; infra-is-code).
- Secret hygiene (gitleaks/self-check before every commit/push).
- File ledger is the durable source of truth; the coordinator never ends its turn with work
  remaining and never asks the user to continue.
- One in-flight unit per hot file; parallelize across non-overlapping files; chains ≤3–4 deep.

## Mission authoring (if you add a mission skill)

Every mission `SKILL.md` must include:

- `## Required skills` — core + one adapter; pointer to `references/composition.md`
- `## Optional skills` — coordinator-only; Activate when / If unavailable
- `## Worker skills` — per role (@grok builder, etc.); injected via DISPATCH
- `## Deferred missions` — table routing out-of-scope work
- T-FINAL readiness doc: **`fleet-outcome` YAML** first ([fleet-outcome.md](../autonomous-fleet-core/references/fleet-outcome.md)), then **Recommended next missions**

Do not author a second mission loader — chains and conditional DAGs belong in `fleet-program`.
