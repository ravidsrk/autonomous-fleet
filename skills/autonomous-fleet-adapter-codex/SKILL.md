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
  version: "1.1.4"
  fleet-component: "adapter"
---


# Adapter: Codex

Runtime: OpenAI Codex (app, IDE extension, or CLI). The coordinator is the main thread; workers
are Codex subagents or shell-driven sessions in git worktrees. No separate orchestration daemon —
the FILE LEDGER is the durable source of truth. Branch prefix: use `BRANCH_PREFIX` from core
self-orientation (default `fleet/`; recorded in DECISIONS.md).

Enable goals if `/goal` is missing: `codex features enable goals` or `features.goals = true` in
`config.toml`.

## PRIMITIVE SUPPORT MATRIX (issue #93 — honest per-primitive status)

| Primitive | Status | Mechanic |
|-----------|--------|----------|
| PLACE | real | `git worktree add` (+ optional container-use) |
| SPAWN_WORKER | real | fresh `codex` session / `codex exec` (headless) |
| DISPATCH | real | role-scoped prompt |
| WAIT | **degraded** | no blocking event API — `poll-ledger.sh` ledger polling |
| INSPECT | real | shell + `gh pr list` |
| WORKER_DONE | real | worker return + ledger write |
| ASK / REPLY | **absent** | no blocking worker→coordinator question exists on this host; workers get DECISION DEFAULTS up front and write `BLOCKED` to the ledger when a question is unanswerable — a documented FALLBACK, not the engine primitive |
| OPEN_PR / MERGE_PR / CLEANUP | real | `gh` + worktree remove |
| SYNC_TASK_STATE | **degraded** | ledger-only (no durable native task view) |
| SET_GOAL family (9–12) | real (interactive) / **inert headless** | `/goal` in the app; `codex exec` is single-shot |
| LOOP_POLL | **degraded** | automations/cron; unverified end-to-end |
| CONTINUE_WORKER | asserted | `codex exec resume <thread>` — verify on your CLI version (#91) |

## PRECONDITIONS

A git repo (REPO_ROOT resolvable) · `gh auth status` via shell (else local merge-commits into
BASE) · git worktree support · gitleaks availability checked · BASE exists (create off the default
branch at current HEAD if absent) · goals feature enabled for SET_GOAL · OPTIONAL: container-use
MCP (`codex mcp add container-use -- container-use stdio`, needs Docker) for sandboxed container
placement, see PLACE(independent) via container-use below.

Machine-readable preflight requires-block:

```yaml requires
bins: [codex, git, gh]
activity_hooks: true
env: []
auth:
  - check: "gh auth status"
    skip_if_intent: "no_scm"
intent_gated:
  scm: "willClaimExistingPR"
```

## CONCURRENCY MODEL

Codex parallelism is via subagents — multiple can run concurrently within one coordinator turn.
There is no persistent external task daemon, so:

- The FILE LEDGER (`docs/<mission>-progress.md`) is the durable source of truth across turns.
- A "worker" is either a subagent (for self-contained units) or a worktree-scoped session the
  coordinator drives via shell (for units needing an isolated branch for their own PR).

## PRIMITIVE → CODEX MECHANIC

### PLACE(kind)
- `independent` → `git worktree add ../<repo>-<slug>-<run_short> -b <BRANCH_PREFIX><slug>-<run_short> BASE`.
- `dependent` → current checkout/branch (fresh subagent or sub-session; no new worktree).

### PLACE(independent) via container-use (optional: isolated container + branch + sandbox)
Register: `codex mcp add container-use -- container-use stdio` (needs Docker). PLACE(independent) MAY
then use a container-use ENVIRONMENT instead of a host `git worktree` — the canonical loop is in
`engine.md` → CONTAINER-USE-PLACEMENT. VERIFIED on a live host: a `codex exec` worker created an
isolated `ubuntu` container on its own branch `container-use/<env>`.

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

**Non-busy poll:** use `./scripts/poll-ledger.sh --ledger docs/<mission>-progress.md --task <id>
--expect '<flag>=t'` between `codex exec` invocations instead of tight loops. Emit trace before
each ledger update (TRACE EMISSION below). Gap 1 status: ledger-poll + helper script (degraded OK).

### INSPECT() — non-destructive
Read FILE LEDGER + `git worktree list` + `gh pr list --base BASE` via shell.

### WORKER_DONE / ASK / REPLY
- WORKER_DONE: worker writes ledger flags + returns summary; that return IS completion.
- ASK/REPLY: give workers DECISION DEFAULTS up front; unanswerable → BLOCKED in ledger; coordinator
  resolves next turn — never escalates to user.

### OPEN_PR / MERGE_PR(conflict-aware) / CLEANUP
Same as other adapters: `gh pr create`, conflict-aware rebase + re-review, `gh pr merge --merge`
(NEVER squash), delete branch. CLEANUP (WT_CLEAN gate): verify MERGED + branch-deleted FIRST;
apply core engine guard clauses — NEVER remove the active/unmerged/dirty worktree; then
`git worktree remove ../<repo>-<slug>-<run_short>`; set task-row `WT_CLEAN=true`; pull BASE.

### SYNC_TASK_STATE(task, status)
Update FILE LEDGER flag. (No external task daemon — ledger is the task view.)

### SET_GOAL(condition) / UPDATE_GOAL / GOAL_COMPLETE / GOAL_BLOCKED

Codex exposes `/goal` in the INTERACTIVE thread composer (pair with `/plan` for ambiguous scope).
HEADLESS CAVEAT: `codex exec` (the unattended path the headless runner uses) is SINGLE-SHOT and does
NOT interpret slash commands — a `/goal ...` string in an exec prompt is inert text, and exec runs
one turn then stops. So for headless codex there is no native goal/continuation harness: drive
continuation with an EXTERNAL LOOP_POLL (cron / a loop that re-invokes `codex exec` on the same repo)
that re-runs until the ledger's DONE condition holds. The `/goal` mechanic below is for interactive
sessions only.

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

## TRACE EMISSION (live coordinator)

Before every ledger write, append one JSONL event:

```bash
python3 <SUBSTRATE>/emit_trace.py emit .fleet/runs/<run_id>/ \
  --primitive WAIT --role COORDINATOR --status started \
  --task-id <task> --id-only
```

Chain worker events with `--parent-event`. See `docs/guide/16-trace-schema.md`.

## CODEX NOTES

- Default role mapping when mission does not override: Codex subagent builds, fresh subagent
  reviews (build-blind), coordinator or integrator opens/merges PRs.

> **Reviewer isolation on this host — single-vendor caveat (issue #88).**
> A fresh Codex subagent reviewing a Codex build is build-blind as
> **instructed** isolation: fresh context, handed only the diff + acceptance
> criteria, write-isolated. It is NOT the mechanical cross-vendor /
> separate-process guarantee (Orca's topology) — a same-vendor reviewer can
> share the builder's blind spots, and nothing in this runtime makes seeing
> the build session physically impossible. Record
> `reviewer_mode: same-vendor-instructed` in DECISIONS.md and the run
> outcome. Scope of the "structural" claim: engine.md REVIEW step.

- File ledger is sacred — update at every lifecycle change before yielding the turn.
- One in-flight unit per hot file; parallelize across non-overlapping files.


## RESUMABILITY + REVIEWER ISOLATION (Wave 3 contract)

- run_short: every isolated branch and worktree carries the active run's 6-hex suffix
  (`<BRANCH_PREFIX><slug>-<run_short>`, `../<repo>-<slug>-<run_short>`, run_short = the 6-hex tail of
  the run_id) so parallel runs/checkouts never collide on a bare slug.
  `<SUBSTRATE>/validate_namespacing.py` enforces this.
- CONTINUE_WORKER(role, placement, session_handle): resume the worker thread (`codex exec resume <thread>`); else ALIAS to SPAWN_WORKER. Re-attach only for `live`-classified
  rows (per `recovery_scan.py`); never re-attach a session whose PR merged or branch is gone. When a
  row's `RESUME_COUNT` hits `MAX_RESUME_ATTEMPTS` (3), escalate instead of continuing.
- Reviewer isolation: when role==reviewer, launch the worker via
  `scripts/run-sandboxed.sh --role reviewer -- <reviewer-cli>` so the candidate tree is read-only and
  only `.fleet/runs/<run_id>/` is writable.
