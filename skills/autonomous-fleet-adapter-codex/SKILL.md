---
name: autonomous-fleet-adapter-codex
description: >-
  The CODEX adapter for autonomous-fleet-core. Maps each engine PRIMITIVE to OpenAI Codex
  mechanics — subagents, git worktrees, shell for git/gh, and the file ledger as durable
  truth. Load alongside autonomous-fleet-core when running a mission in Codex (app, IDE, or
  CLI). The coordinator IS the main Codex thread; workers are subagents or worktree-scoped
  sessions; the file ledger survives compaction.
license: MIT
compatibility: Requires Codex with goals enabled (features.goals), git worktrees, and gh CLI
metadata:
  author: "ravidsrk"
  version: "1.1.0"
  fleet-component: "adapter"
---


# Adapter: Codex

Runtime: OpenAI Codex (app, IDE extension, or CLI). The coordinator is the main thread; workers
are Codex subagents or shell-driven sessions in git worktrees. No separate orchestration daemon —
the FILE LEDGER is the durable source of truth. Branch prefix: use `BRANCH_PREFIX` from core
self-orientation (default `fleet/`; recorded in DECISIONS.md).

Enable goals if `/goal` is missing: `codex features enable goals` or `features.goals = true` in
`config.toml`.

## PRECONDITIONS

A git repo (REPO_ROOT resolvable) · `gh auth status` via shell (else local merge-commits into
BASE) · git worktree support · gitleaks availability checked · BASE exists (create off the default
branch at current HEAD if absent) · goals feature enabled for SET_GOAL · OPTIONAL: container-use
MCP (`codex mcp add container-use -- container-use stdio`, needs Docker) for sandboxed container
placement, see PLACE(independent) via container-use below.

## CONCURRENCY MODEL

Codex parallelism is via subagents — multiple can run concurrently within one coordinator turn.
There is no persistent external task daemon, so:

- The FILE LEDGER (`docs/<mission>-progress.md`) is the durable source of truth across turns.
- A "worker" is either a subagent (for self-contained units) or a worktree-scoped session the
  coordinator drives via shell (for units needing an isolated branch for their own PR).

## PRIMITIVE → CODEX MECHANIC

### PLACE(kind)
- `independent` → `git worktree add ../<repo>-<slug> -b <BRANCH_PREFIX><slug> BASE`.
- `dependent` → current checkout/branch (fresh subagent or sub-session; no new worktree).

### PLACE(independent) via container-use (optional: isolated container + branch + sandbox)
When the container-use MCP is configured (`codex mcp add container-use -- container-use stdio`),
PLACE(independent) MAY use a container-use ENVIRONMENT instead of a host `git worktree`, closing the
OS-sandbox gap (the worker runs in an isolated Linux container, not the host) and the isolation gap
(each environment is its own git branch) together. VERIFIED WORKING on a live host: a `codex exec`
worker with this MCP called `environment_create` and produced an isolated `ubuntu` container on its
own branch `container-use/<env>`.
- SPAWN_WORKER(independent): launch the codex worker with the container-use MCP available; it does
  ALL file/shell work through the environment (`environment_create` -> env id + branch
  `container-use/<env>`, then `environment_file_write` / `environment_run_cmd`). One env per unit.
- INSPECT(): `container-use list` / `log <env>` / `diff <env>` (non-destructive).
- OPEN_PR / SHIP: `container-use checkout <env>` (local branch from `container-use/<env>`), push,
  `gh pr create --base BASE`; OR `container-use merge <env>` into BASE. The SHA-pin + conflict-aware
  rules from engine.md still apply.
- CLEANUP: `container-use delete <env>` (or `--all`) instead of `git worktree remove`.
- FALLBACK: no container-use MCP -> the plain `git worktree` path above. See docs/adopt-container-use.md.

### SPAWN_WORKER(role, placement)
- Subagent path: launch via Codex subagent spawn with role-scoped prompt (builder / reviewer /
  integrator), unit spec, ledger path, REPO_ROOT, MAINTAINER, BRANCH_PREFIX, completion contract.
  Use full-auto / skip-permissions flags per Codex settings.
- Worktree sub-session: `git worktree add` per PLACE(independent), drive work in that directory
  via shell.
- "Ready" is immediate for subagents; for sub-sessions, when checkout exists and deps installed.

### DISPATCH(task, handle)
Build payload: (1) mission `## Worker skills` for the role per core engine.md; (2) task spec and
completion contract. Subagent: full payload in spawn prompt. Sub-session: write payload into
worktree and begin via shell.

### WAIT(types, timeout)
Subagents return when done — collect structured results. For sub-sessions, poll ledger + git state.
Timeout = checkpoint, not failure. Active worker = alive; do not abort.

### INSPECT() — non-destructive
Read FILE LEDGER + `git worktree list` + `gh pr list --base BASE` via shell.

### WORKER_DONE / ASK / REPLY
- WORKER_DONE: worker writes ledger flags + returns summary; that return IS completion.
- ASK/REPLY: give workers DECISION DEFAULTS up front; unanswerable → BLOCKED in ledger; coordinator
  resolves next turn — never escalates to user.

### OPEN_PR / MERGE_PR(conflict-aware) / CLEANUP
Same as other adapters: `gh pr create`, conflict-aware rebase + re-review, `gh pr merge --merge`
(NEVER squash), `git worktree remove`.

### SYNC_TASK_STATE(task, status)
Update FILE LEDGER flag. (No external task daemon — ledger is the task view.)

### SET_GOAL(condition) / UPDATE_GOAL / GOAL_COMPLETE / GOAL_BLOCKED

Codex exposes `/goal` in the thread composer (pair with `/plan` for ambiguous scope).

**SET_GOAL:** `/goal <condition>` after ledger init. Shape with `/plan` first when scope is
ambiguous. Record condition under `## Runtime goal` in ledger per `runtime-goals.md`. Condition must
reference `docs/` paths.

**UPDATE_GOAL:** Log in ledger `LAST_UPDATE`; Codex goal UI shows progress automatically.

**GOAL_COMPLETE:** After TERMINATE checks (ledger, readiness, `validate-fleet-outcome.sh`), mark
goal done in Codex UI or start next thread. Do not declare done before file validation.

**GOAL_BLOCKED:** Pause goal; write `fleet-outcome.status: blocked` in readiness.

**LOOP_POLL:** Codex automations or `/loop`-equivalent scheduling for CI polling only — not
mission sequencing.

**Headless / non-interactive:** Codex non-interactive mode with goal in prompt — see
`scripts/run-mission-headless.sh codex …`.

## DIAGNOSTICS

- Worker returned without ledger write: re-read summary; relaunch if incomplete (idempotent).
- Context pressure: CONTEXT HANDOFF block in ledger for fresh coordinator resume.

## CODEX NOTES

- Default role mapping when mission does not override: Codex subagent builds, fresh subagent
  reviews (build-blind), coordinator or integrator opens/merges PRs.
- File ledger is sacred — update at every lifecycle change before yielding the turn.
- One in-flight unit per hot file; parallelize across non-overlapping files.