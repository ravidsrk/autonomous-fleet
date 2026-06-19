---
name: autonomous-fleet-adapter-claude-code
description: >-
  The CLAUDE CODE adapter for autonomous-fleet-core. Maps each engine PRIMITIVE to Claude Code's
  native mechanics — subagents via the Task tool, git worktrees for isolation, the Bash tool for
  git/gh, and TodoWrite as the live task mirror. Load this alongside autonomous-fleet-core when
  running a mission in Claude Code instead of Orca. Because Claude Code has no separate
  orchestration runtime, the coordinator IS the main Claude Code session and workers are subagents
  or worktree-scoped sub-sessions; the file ledger is the durable source of truth and TodoWrite
  mirrors it.
---

# Adapter: Claude Code

Runtime: Claude Code (the coordinator is the main session; workers are subagents via the Task
tool, or sub-sessions scoped to a git worktree). No separate orchestration daemon — so the FILE
LEDGER is the authority and TodoWrite is the live mirror. Branch prefix: use `BRANCH_PREFIX` from
core self-orientation (default `fleet/`; recorded in DECISIONS.md).

This adapter resolves the core's PRIMITIVES to Claude Code mechanics. Where Claude Code cannot
provide a primitive natively (e.g. cross-session blocking message queues), the adapter substitutes
the file ledger + polling, and says so.

## PRECONDITIONS (the core calls for these; here's the Claude Code form)
A git repo (REPO_ROOT resolvable) · `gh auth status` via Bash (else local merge-commits into BASE)
· git worktree support · gitleaks availability checked · BASE exists (create off the default
branch at current HEAD if absent). The coordinator confirms these with the Bash tool at start.

## CONCURRENCY MODEL (important difference from Orca)
Claude Code parallelism is via SUBAGENTS launched with the Task tool — multiple can run
concurrently within one coordinator turn. There is no persistent external task daemon, so:
- The FILE LEDGER (docs/<mission>-progress.md) is the durable source of truth across turns.
- TodoWrite mirrors the ledger for live visibility but is NOT the source of truth (it is
  per-session).
- A "worker" is either a subagent (Task tool, for self-contained units) or a worktree-scoped
  sub-session the coordinator drives via Bash + the agent CLI (for units needing an isolated
  long-running checkout). Prefer subagents for review and bounded build units; use a worktree
  sub-session when the unit needs an isolated branch for its own PR.

## PRIMITIVE → CLAUDE CODE MECHANIC

### PLACE(kind)
- `independent` → `git worktree add ../<repo>-<slug> -b <BRANCH_PREFIX><slug> BASE` (isolated
  checkout on its own branch for a parallel PR).
- `dependent` → operate in the current checkout/branch (a fresh subagent or sub-session; no new
  worktree).

### SPAWN_WORKER(role, placement)
- Subagent path (preferred for self-contained build/review units): launch via the Task tool with a
  role-scoped prompt (builder / reviewer / integrator) that includes the unit spec, the acceptance
  criteria, the ledger path, and the completion contract (write results back to the ledger + return
  a structured summary). Subagents run in auto mode by default.
- Worktree sub-session path (for units needing an isolated long-running checkout): `git worktree
  add` per PLACE(independent), then drive the agent CLI in that directory via Bash. Use the tool's
  non-interactive/auto flag.
- "Ready" is immediate for subagents; for a sub-session, when its checkout exists and deps are
  installed.

### DISPATCH(task, handle)
Subagent: pass the task spec in the Task-tool prompt (dispatch == launch). Sub-session: write the
task spec into the worktree and start the agent CLI on it via Bash.

### WAIT(types, timeout)
Subagents return to the coordinator when done — collect their structured results. For sub-sessions
or long Bash-driven work, poll: re-read the FILE LEDGER and check the worktree's git state /
process. A subagent still running = alive; do not abort it. There is no busy-wait daemon — the
coordinator advances when a subagent returns or a polled ledger flag flips.

### INSPECT() — non-destructive
Read the FILE LEDGER (docs/<mission>-progress.md) and `git worktree list` + `gh pr list --base
BASE` via Bash. TodoWrite reflects current state for visibility. None of these consume anything.

### WORKER_DONE / ASK / REPLY
- WORKER_DONE: a subagent writes its result into the ledger (flags + files modified + summary) and
  returns a structured summary to the coordinator; that return IS the completion signal. A
  sub-session writes a completion line into the ledger that the coordinator polls.
- ASK/REPLY: a subagent cannot block on a coordinator mid-run. Resolve blocking questions by giving
  workers the mission's DECISION DEFAULTS up front so they decide autonomously and record the
  decision in DECISIONS.md. If a genuinely unanswerable decision arises, the worker records it as a
  BLOCKED item in the ledger and returns; the coordinator resolves it on the next turn from the
  defaults — never escalates to the user.

### OPEN_PR / MERGE_PR(conflict-aware) / CLEANUP — all via Bash + gh
- OPEN_PR: `gh pr create --base BASE --head <BRANCH_PREFIX><slug> --title "<title>" --body "<body>"`.
- MERGE_PR: check conflicts (`gh pr view <n> --json mergeable,mergeStateStatus` or trial rebase).
  If conflicts: `git fetch origin BASE && git rebase origin/BASE`, resolve, re-test green,
  re-review (relaunch the reviewer subagent on the rebased diff) if logic changed, force-push.
  Then `gh pr merge <n> --merge --delete-branch` (merge commit, commits preserved, NEVER
  `--squash`).
- CLEANUP: `git worktree remove ../<repo>-<slug>` for the merged unit; pull BASE.

### SYNC_TASK_STATE(task, status)
Update the FILE LEDGER flag and the TodoWrite entry. (No external task daemon to sync — the ledger
+ TodoWrite together are the task view.)

## DIAGNOSTICS
- A subagent that returned without writing its ledger result: re-read its returned summary; if
  incomplete, relaunch the unit (it's idempotent against the ledger — a unit already MERGED is
  skipped). Never lose a merged unit.
- Coordinator context pressure: write the CONTEXT HANDOFF block into the ledger (per the core) so a
  fresh coordinator session resumes — this matters MORE in Claude Code, where the coordinator is
  itself a session with a context limit and there's no external daemon holding state.

## CLAUDE CODE NOTES
- Keep build units bounded so a subagent can finish one within its context; decompose large units
  rather than handing a subagent something it can't complete in one run.
- The file ledger is sacred here — it is the ONLY thing that survives across coordinator turns and
  session restarts. Update it at every lifecycle change, before yielding the turn.
- One in-flight unit per hot file still holds: do not run two subagents editing the same file
  concurrently. Parallelize subagents across non-overlapping files.
