---
name: autonomous-fleet-adapter-grok
description: >-
  The GROK adapter for autonomous-fleet-core. Maps each engine PRIMITIVE to Grok Build
  mechanics — subagents via the Task tool, git worktrees for isolation, the Shell tool for
  git/gh, and the file ledger as the durable source of truth. Load this alongside
  autonomous-fleet-core when running a mission in Grok instead of Orca. Because Grok has no
  separate orchestration daemon, the coordinator IS the main Grok session and workers are
  subagents (Task tool) or worktree-scoped shell-driven sessions; the file ledger is the
  authority.
license: MIT
compatibility: Requires Grok Build with Task tool, git worktrees, and gh CLI
metadata:
  author: "ravidsrk"
  version: "1.1.6"
  fleet-component: "adapter"
---


# Adapter: Grok

Runtime: Grok Build (the coordinator is the main session; workers are subagents via the Task
tool, or shell-driven sessions scoped to a git worktree). No separate orchestration daemon — the
FILE LEDGER is the durable source of truth across turns. Branch prefix: use `BRANCH_PREFIX` from
core self-orientation (default `fleet/`; recorded in DECISIONS.md).

This adapter resolves the core's PRIMITIVES to Grok mechanics. Where Grok cannot provide a
primitive natively (e.g. cross-session blocking message queues), the adapter substitutes the file
ledger + polling, and says so.

## PRIMITIVE SUPPORT MATRIX (issue #93 — honest per-primitive status)

| Primitive | Status | Mechanic |
|-----------|--------|----------|
| PLACE | real | `git worktree add` (+ optional container-use) |
| SPAWN_WORKER | real | Grok Task tool / subagent spawn |
| DISPATCH | real | role-scoped prompt |
| WAIT | **degraded** | no blocking event API — ledger polling |
| INSPECT | real | shell |
| WORKER_DONE | real | worker return + ledger write |
| ASK / REPLY | **absent** | no blocking worker→coordinator question exists on this host; workers get DECISION DEFAULTS up front and write `BLOCKED` to the ledger — a documented FALLBACK, not the engine primitive |
| OPEN_PR / MERGE_PR / CLEANUP | real | `gh` + worktree remove |
| SYNC_TASK_STATE | **degraded** | ledger-only |
| SET_GOAL family (9–12) | real | `/goal`, `update_goal` |
| LOOP_POLL | real | `/loop`, `scheduler_create` |
| CONTINUE_WORKER | real | `grok --resume <SESSION_ID>` / `-c` for most-recent (VERIFIED grok 0.2.82, issue #91) |

## PRECONDITIONS (the core calls for these; here's the Grok form)
A git repo (REPO_ROOT resolvable) · `gh auth status` via Shell (else local merge-commits into BASE)
· git worktree support · gitleaks availability checked · BASE exists (create off the default
branch at current HEAD if absent). The coordinator confirms these with Shell at start. OPTIONAL:
container-use MCP (`grok mcp add container-use -- container-use stdio`, needs Docker) for sandboxed
container placement, see PLACE(independent) via container-use below.

Machine-readable preflight requires-block:

```yaml requires
bins: [grok, git, gh]
activity_hooks: true
env: []
auth:
  - check: "gh auth status"
    skip_if_intent: "no_scm"
intent_gated:
  scm: "willClaimExistingPR"
```

## CONCURRENCY MODEL (important difference from Orca)
Grok parallelism is via SUBAGENTS launched with the Task tool — multiple can run concurrently.
There is no persistent external task daemon, so:
- The FILE LEDGER (`docs/<mission>-progress.md`) is the durable source of truth across turns.
- A "worker" is either a subagent (Task tool, for self-contained units) or a worktree-scoped
  session the coordinator drives via Shell (for units needing an isolated long-running checkout).
  Prefer subagents for review and bounded build units; use a worktree sub-session when the unit
  needs an isolated branch for its own PR.

## PRIMITIVE → GROK MECHANIC

### PLACE(kind)
- `independent` → `git worktree add ../<repo>-<slug>-<run_short> -b <BRANCH_PREFIX><slug>-<run_short> BASE` (isolated
  checkout on its own branch for a parallel PR).
- `dependent` → operate in the current checkout/branch (a fresh subagent or sub-session; no new
  worktree).

### PLACE(independent) via container-use (optional: isolated container + branch + sandbox)
Register: `grok mcp add container-use -- container-use stdio` (needs Docker). PLACE(independent) MAY
then use a container-use ENVIRONMENT instead of a host `git worktree` — the canonical loop is in
`engine.md` → CONTAINER-USE-PLACEMENT. The registration is verified on this host; a full live run is
gated by Grok's own auth (headless Grok hits `Auth(AuthorizationRequired)`), so exercise it once Grok
login is configured. The engine and loop are proven on the Claude Code and Codex adapters.

### SPAWN_WORKER(role, placement)
- Subagent path (preferred for self-contained build/review units): launch via the Task tool with a
  role-scoped prompt (builder / reviewer / integrator) that includes the unit spec, acceptance
  criteria, ledger path, REPO_ROOT, MAINTAINER, BRANCH_PREFIX, and the completion contract (write
  results back to the ledger + return a structured summary). Let the host pick its DEFAULT grok model
  unless the mission specifies otherwise; if you pass `-m <model>`, use an id the installed grok
  actually accepts (the literal `composer-2.5-fast` is rejected as unknown — do not hard-code it).
- Worktree sub-session path (for units needing an isolated long-running checkout): `git worktree
  add` per PLACE(independent), then drive work in that directory via Shell.
- "Ready" is immediate for subagents; for a sub-session, when its checkout exists and deps are
  installed.

### DISPATCH(task, handle)
Build the dispatch payload: (1) if the mission's `## Worker skills` lists skills for this worker's
role, prepend **Worker skills:** "Activate and follow: `<names>`" per core engine.md; (2) the task
spec and completion contract. Subagent: pass the full payload in the Task-tool prompt (dispatch ==
launch). Sub-session: write the payload into the worktree and begin work there via Shell.

### WAIT(types, timeout)
Subagents return to the coordinator when done — collect their structured results. For sub-sessions
or long Shell-driven work, poll: re-read the FILE LEDGER and check the worktree's git state. A
subagent still running = alive; do not abort it. There is no busy-wait daemon — the coordinator
advances when a subagent returns or a polled ledger flag flips. Timeout = checkpoint, not failure.

**Non-busy poll (mechanical):** between coordinator turns, prefer
`./scripts/poll-ledger.sh --ledger docs/<mission>-progress.md --task <id> --expect '<flag>=t'`
instead of tight spin loops. Emit trace **before** each ledger flag flip (see TRACE EMISSION).
Landscape Gap 1 is **degraded but closed** for Grok: ledger-poll + `poll-ledger.sh` replaces a
daemon WAIT; Claude Code/Orca have native notifications.

### INSPECT() — non-destructive
Read the FILE LEDGER (`docs/<mission>-progress.md`) and `git worktree list` + `gh pr list --base
BASE` via Shell. None of these consume anything.

### WORKER_DONE / ASK / REPLY
- WORKER_DONE: a subagent writes its result into the ledger (flags + files modified + summary) and
  returns a structured summary to the coordinator; that return IS the completion signal. A
  sub-session writes a completion line into the ledger that the coordinator polls.
- ASK/REPLY: a subagent cannot block on a coordinator mid-run. Resolve blocking questions by giving
  workers the mission's DECISION DEFAULTS up front so they decide autonomously and record the
  decision in DECISIONS.md. If a genuinely unanswerable decision arises, the worker records it as a
  BLOCKED item in the ledger and returns; the coordinator resolves it on the next turn from the
  defaults — never escalates to the user.

### OPEN_PR / MERGE_PR(conflict-aware) / CLEANUP — all via Shell + gh
- OPEN_PR: `gh pr create --base BASE --head <BRANCH_PREFIX><slug>-<run_short> --title "<title>" --body "<body>"`.
- MERGE_PR: check conflicts (`gh pr view <n> --json mergeable,mergeStateStatus` or trial rebase).
  If conflicts: `git fetch origin BASE && git rebase origin/BASE`, resolve, re-test green,
  re-review (relaunch the reviewer subagent on the rebased diff) if logic changed, force-push.
  Then `gh pr merge <n> --merge --delete-branch` (merge commit, commits preserved, NEVER
  `--squash`).
- CLEANUP (WT_CLEAN gate): verify MERGED + branch-deleted FIRST. Apply core engine guard clauses —
  NEVER remove the active worktree; NEVER remove an unmerged or dirty worktree. Then
  `git worktree remove ../<repo>-<slug>-<run_short>`; set task-row `WT_CLEAN=true` in the ledger;
  pull BASE.

### SYNC_TASK_STATE(task, status)
Update the FILE LEDGER flag for the task. (No external task daemon to sync — the ledger is the
task view.)

### SET_GOAL(condition) / UPDATE_GOAL / GOAL_COMPLETE / GOAL_BLOCKED

Grok Build exposes goal mode via `/goal` and the `update_goal` tool (requires goal feature enabled).

**SET_GOAL:** At mission or campaign start (after ledger init), run `/goal <condition>` OR instruct
the user to run it if the tool is unavailable in the session. Write the same condition under
`## Runtime goal` in the ledger per `runtime-goals.md`. Condition must reference `docs/` ledger
and readiness paths — not model self-assessment alone.

**UPDATE_GOAL:** Call `update_goal(message: "<phase>: <summary>")` at major transitions (node
done, wave merged, validation passed). Update `LAST_UPDATE` in the ledger.

**GOAL_COMPLETE:** Only after core TERMINATE checks: re-read ledger, readiness exists,
the readiness fleet-outcome validates (`python3 <SUBSTRATE>/validate_fleet_outcome.py`). Then
`update_goal(completed: true, message: "<final summary>")`. Clear with `/goal clear` if needed.

**GOAL_BLOCKED:** `update_goal(blocked_reason: "<reason>")` when mission hits hard external
dependency or unrecoverable circuit-breaker. Set `fleet-outcome.status: blocked` in readiness.

**LOOP_POLL (optional):** `/loop <interval> <prompt>` or `scheduler_create` for CI polling —
not for mission sequencing (use `fleet-program`). `monitor` for streaming test/log events.
Background shell: `background: true` on `run_terminal_command`; poll with
`get_command_or_subagent_output`.

**Headless:** `grok -p "<prompt with /goal condition>" --max-turns N --yolo` — see
`scripts/run-mission-headless.sh`.

## DIAGNOSTICS
- A subagent that returned without writing its ledger result: re-read its returned summary; if
  incomplete, relaunch the unit (it's idempotent against the ledger — a unit already MERGED is
  skipped). Never lose a merged unit.
- Coordinator context pressure: write the CONTEXT HANDOFF block into the ledger (per the core) so a
  fresh coordinator session resumes — critical in Grok, where the coordinator is itself a session
  with a context limit and there's no external daemon holding state.

## TRACE EMISSION (live coordinator)

Trace **before** ledger write on every transition (engine.md TRACE EMISSION). Append events with:

```bash
python3 <SUBSTRATE>/emit_trace.py emit .fleet/runs/<run_id>/ \
  --primitive DISPATCH --role COORDINATOR --status started \
  --task-id <task> --id-only
```

Capture the printed event id; pass `--parent-event <id>` on worker `COMMIT`/`INSPECT` rows.
If `manifest.json` is not present yet, add `--mission <slug> --run-id <run_id>`.

## GROK NOTES
- Keep build units bounded so a subagent can finish one within its context; decompose large units
  rather than handing a subagent something it can't complete in one run.
- The file ledger is sacred — it is the ONLY thing that survives across coordinator turns and
  session restarts. Update it at every lifecycle change, before yielding the turn.
- One in-flight unit per hot file still holds: do not run two subagents editing the same file
  concurrently. Parallelize subagents across non-overlapping files.
- Default role mapping when a mission does not override: Grok subagent builds, a fresh Grok
  subagent reviews (build-blind), coordinator or integrator subagent opens/merges PRs.

> **Reviewer isolation on this host — single-vendor caveat (issue #88).**
> A fresh Grok subagent reviewing a Grok build is build-blind as
> **instructed** isolation: fresh context, handed only the diff + acceptance
> criteria, write-isolated. It is NOT the mechanical cross-vendor /
> separate-process guarantee (Orca's topology) — a same-vendor reviewer can
> share the builder's blind spots, and nothing in this runtime makes seeing
> the build session physically impossible. Record
> `reviewer_mode: same-vendor-instructed` in DECISIONS.md and the run
> outcome. Scope of the "structural" claim: engine.md REVIEW step.



## RESUMABILITY + REVIEWER ISOLATION (Wave 3 contract)

Follow the single-sourced contract in
`autonomous-fleet-core` → `references/adapter-contract.md` (issue #89 — do
NOT re-inline it here; the drift lint fails copies). This adapter's only
runtime-specific binding:

- CONTINUE_WORKER binding: `grok --resume <SESSION_ID>` (or `-c`/`--continue` for the cwd's most recent; `--fork-session` to branch) — VERIFIED grok 0.2.82; else ALIAS to SPAWN_WORKER
