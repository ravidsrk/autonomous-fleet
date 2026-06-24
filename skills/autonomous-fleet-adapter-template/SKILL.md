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
  version: "1.1.0"
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

Machine-readable preflight requires-block:

```yaml requires
bins: [git, gh]
env: []
auth:
  - check: "gh auth status"
    skip_if_intent: "no_scm"
intent_gated:
  scm: "willClaimExistingPR"
```

## PRIMITIVE → <TOOL> MAPPING (fill every one)

### PLACE(kind)
- `independent` → <how your tool makes an isolated checkout on its own branch off BASE>.
- `independent` via container-use (OPTIONAL) → if your runtime can register the container-use MCP
  (`<tool> mcp add container-use -- container-use stdio`, needs Docker), reuse the canonical sandboxed
  loop in core `engine.md` → CONTAINER-USE-PLACEMENT and record your registration command +
  verification status here. Omit this bullet if unsupported.
- `dependent` → <how your tool runs a fresh worker in the current checkout/branch>.

### SPAWN_WORKER(role, placement) → handle in auto/max mode
<the command(s) to create a worker in the given placement, with the tool's auto/skip-permissions +
max-effort flags. State what "ready" means and how you wait for it before DISPATCH.>
**CAPABILITY TIERS.** Declare the worker-spawn mechanisms your runtime offers, richest first (e.g.
native multi-agent teams → subagents → a single-session/inbox fallback) and which this adapter uses.
A thinner runtime may collapse to one tier — say so explicitly rather than leaving it implied.
**ROLE → AGENT CLI.** Map each role to a concrete CLI honouring the cross-vendor rule: builder
`@codex` (or `@grok` for design missions), a fresh build-blind reviewer `@claude`, integrator
`@claude`. With only one vendor available, keep terminal separation (a fresh reviewer session) and
record the single-vendor mode.

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

### SET_GOAL / UPDATE_GOAL / GOAL_COMPLETE / GOAL_BLOCKED (if host supports goal mode)
<how your runtime binds native goal APIs to ledger DONE. See core `references/runtime-goals.md`.
If no goal API (daemon coordinator like Orca), document ledger-only mapping.>

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


## RESUMABILITY + REVIEWER ISOLATION (Wave 3 contract)

- run_short: every isolated branch and worktree carries the active run's 6-hex suffix
  (`<BRANCH_PREFIX><slug>-<run_short>`, `../<repo>-<slug>-<run_short>`, run_short = the 6-hex tail of
  the run_id) so parallel runs/checkouts never collide on a bare slug.
  `scripts/validate_namespacing.py` enforces this.
- CONTINUE_WORKER(role, placement, session_handle): <declare this runtime's restore command, e.g. sessionId / thread id, or 'none -> alias'>. Re-attach only for `live`-classified
  rows (per `recovery_scan.py`); never re-attach a session whose PR merged or branch is gone. When a
  row's `RESUME_COUNT` hits `MAX_RESUME_ATTEMPTS` (3), escalate instead of continuing.
- Reviewer isolation: when role==reviewer, launch the worker via
  `scripts/run-sandboxed.sh --role reviewer -- <reviewer-cli>` so the candidate tree is read-only and
  only `.fleet/runs/<run_id>/` is writable.

## TRACKER (issue binding) — fill in

Declare this adapter's TRACKER binding INDEPENDENTLY of its SCM binding (engine.md: gh is the
DEFAULT, not the contract):

- Tracker: `<github-issues | linear | none>` — how the coordinator reads the issue, derives the
  branch name, and marks the issue done.
- SCM: `<gh | glab | ...>` — OPEN_PR against BASE + conflict-aware MERGE_PR (never squash). A
  Linear tracker can pair with a GitHub SCM.
