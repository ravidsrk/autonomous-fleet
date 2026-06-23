---
name: autonomous-fleet-adapter-claude-code
description: >-
  The CLAUDE CODE adapter for autonomous-fleet-core. Maps each engine PRIMITIVE to Claude
  Code's native mechanics — subagents via the Task tool, git worktrees for isolation, the
  Bash tool for git/gh, and TodoWrite as the live task mirror. Load this alongside
  autonomous-fleet-core when running a mission in Claude Code instead of Orca. Because
  Claude Code has no separate orchestration runtime, the coordinator IS the main Claude Code
  session and workers are subagents or worktree-scoped sub-sessions; the file ledger is the
  durable source of truth and TodoWrite mirrors it.
license: MIT
compatibility: Requires Claude Code with Task tool, git worktrees, and gh CLI
metadata:
  author: "ravidsrk"
  version: "1.1.0"
  fleet-component: "adapter"
---


# Adapter: Claude Code

Runtime: Claude Code (the coordinator is the main session; workers are subagents via the Task
tool, or sub-sessions scoped to a git worktree). No separate orchestration daemon — so the FILE
LEDGER is the authority and TodoWrite is the live mirror. Branch prefix: use `BRANCH_PREFIX` from
core self-orientation (default `fleet/`; recorded in DECISIONS.md).

This adapter resolves the core's PRIMITIVES to Claude Code mechanics. Native blocking message
queues now exist under agent teams (SendMessage, automatic delivery, idle notifications); where a
host has them off, the adapter substitutes the file ledger + inbox markers as the FALLBACK, and
says so.

## PRECONDITIONS (the core calls for these; here's the Claude Code form)
A git repo (REPO_ROOT resolvable) · `gh auth status` via Bash (else local merge-commits into BASE)
· git worktree support · gitleaks availability checked · BASE exists (create off the default
branch at current HEAD if absent). The coordinator confirms these with the Bash tool at start.
OPTIONAL: if the container-use MCP is configured (`claude mcp add container-use -- container-use
stdio`, needs Docker), PLACE(independent) can use an isolated container + branch instead of a host
worktree — see PLACE(independent) via container-use below.

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

CAPABILITY TIER (detect once at start, record in DECISIONS.md):
- TEAMS tier if `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` (check env / settings.json). Native
  SendMessage, automatic delivery, idle notifications, shared task list with dependency tracking +
  file locking. Use it for WAIT/ASK/REPLY/SYNC_TASK_STATE directly.
- SUBAGENT tier otherwise (default). Foreground/background subagents via the Task tool. Native
  blocking WAIT and fan-out completion-collect; NO native mid-run ASK (workers decide from DECISION
  DEFAULTS).
- INBOX fallback only when neither holds (teams off AND background tasks disabled, or a degraded
  binary): file markers under docs/.inbox/.
The FILE LEDGER stays the durable cross-turn authority in every tier (the shared task list is
per-session and its status can lag).

### PLACE(kind)
- `independent` → `git worktree add ../<repo>-<slug> -b <BRANCH_PREFIX><slug> BASE` (isolated
  checkout on its own branch for a parallel PR).
- `dependent` → operate in the current checkout/branch (a fresh subagent or sub-session; no new
  worktree).

### PLACE(independent) via container-use (optional: isolated container + branch + sandbox)
Register: `claude mcp add container-use -- container-use stdio` (needs Docker), then allow the
subagent the `mcp__container-use__environment_*` tools. PLACE(independent) MAY then use a
container-use ENVIRONMENT instead of a host `git worktree` — the canonical loop (SPAWN_WORKER /
INSPECT / OPEN_PR / CLEANUP / FALLBACK and the `merge`-bypasses-the-PR-gate warning) lives in
`engine.md` → CONTAINER-USE-PLACEMENT. Verified end to end on a live host (container-use v0.4.2 +
Docker): commands run INSIDE the container (`uname` reports Linux, not the macOS host).

### SPAWN_WORKER(role, placement)
- Subagent path (preferred for self-contained build/review units): launch via the Task tool with a
  role-scoped prompt (builder / reviewer / integrator) that includes the unit spec, the acceptance
  criteria, the ledger path, and the completion contract (write results back to the ledger + return
  a structured summary). Subagents run in auto mode by default.
- Worktree sub-session path (for units needing an isolated long-running checkout): `git worktree
  add` per PLACE(independent), then drive the agent CLI in that directory via Bash. Use the tool's
  non-interactive/auto flag. PLACE(independent) can also bind to native `isolation: worktree`
  subagent frontmatter (or `claude --bg` session worktrees under .claude/worktrees/) rather than
  only a hand-driven `git worktree add`.
- "Ready" is immediate for subagents; for a sub-session, when its checkout exists and deps are
  installed.

### DISPATCH(task, handle)
Build the dispatch payload: (1) if the mission's `## Worker skills` lists skills for this worker's
role, prepend **Worker skills:** "Activate and follow: `<names>`" per core engine.md; (2) the task
spec and completion contract. Subagent: pass the full payload in the Task-tool prompt (dispatch ==
launch). Sub-session: write the payload into the worktree and start the agent CLI on it via Bash.

### WAIT(types, timeout)
- TEAMS tier: do not poll. Teammate messages and idle notifications arrive automatically (the lead
  does not poll for updates); a finished teammate notifies the lead on stop. WAIT == let those
  arrive, then act. Reconcile each against the FILE LEDGER, which is authoritative because
  shared-task status can lag.
- SUBAGENT tier: a FOREGROUND subagent blocks until complete and returns its summary (native
  non-busy WAIT for one worker). For fan-out, launch BACKGROUND subagents (`background: true`, or
  "run in the background", or `CLAUDE_CODE_FORK_SUBAGENT=1`) and collect each result as it returns
  to the main conversation. A still-running subagent is alive, never abort it.
- INBOX fallback: re-read the FILE LEDGER and `docs/.inbox/<task>.done` (completion) / `.ask`
  (blocked question) markers on a bounded cadence via LOOP_POLL or a foreground re-read loop.
A WAIT timeout or empty result is a checkpoint, not a failure (per core).

### INSPECT() — non-destructive
Read the FILE LEDGER (docs/<mission>-progress.md) and `git worktree list` + `gh pr list --base
BASE` via Bash. TodoWrite reflects current state for visibility. None of these consume anything.

### WORKER_DONE / ASK / REPLY
- WORKER_DONE:
  - TEAMS: the teammate marks its shared-list task `completed` and goes idle, auto-notifying the
    lead; it also writes its result into the FILE LEDGER (flags + files + summary). The ledger
    write is the durable signal; the idle notification is the wake.
  - SUBAGENT: the subagent writes its result into the ledger and returns a structured summary; that
    return (foreground) or arriving result message (background) IS the completion signal.
  - INBOX: the worker writes its ledger result and touches `docs/.inbox/<task>.done`.
- ASK / REPLY:
  - TEAMS tier (native): a teammate ASKs the lead with `SendMessage` (or, under required-plan-
    approval, a plan-approval request); the lead REPLYs with `SendMessage` (or approve/reject),
    deciding from the mission DECISION DEFAULTS, never relaying to the user. SendMessage exists only
    with `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`; a SendMessage to a stopped worker auto-resumes it.
  - SUBAGENT tier (no native mid-run ASK): a background subagent that hits an unanswerable decision
    cannot block the coordinator (its prompting tool call just fails). Give every worker the
    DECISION DEFAULTS up front so it decides autonomously and records the choice in DECISIONS.md. If
    still unanswerable, the worker records a BLOCKED item in the ledger and returns; the coordinator
    resolves it next turn from the defaults.
  - INBOX fallback: the worker writes the question to `docs/.inbox/<task>.ask` and BLOCKs in the
    ledger; the coordinator answers from DECISION DEFAULTS into `docs/.inbox/<task>.reply` and
    re-dispatches.
  Never escalate a worker question to the user.

### OPEN_PR / MERGE_PR(conflict-aware) / CLEANUP — all via Bash + gh
- OPEN_PR: `gh pr create --base BASE --head <BRANCH_PREFIX><slug> --title "<title>" --body "<body>"`.
- MERGE_PR: check conflicts (`gh pr view <n> --json mergeable,mergeStateStatus` or trial rebase).
  If conflicts: `git fetch origin BASE && git rebase origin/BASE`, resolve, re-test green,
  re-review (relaunch the reviewer subagent on the rebased diff) if logic changed, force-push.
  Then `gh pr merge <n> --merge --delete-branch` (merge commit, commits preserved, NEVER
  `--squash`).
- CLEANUP: `git worktree remove ../<repo>-<slug>` for the merged unit; pull BASE.

### SYNC_TASK_STATE(task, status)
Update the FILE LEDGER flag and the TodoWrite entry. In TEAMS tier, also mirror to the native
shared task list (pending/in_progress/completed, with dependencies) in addition to the ledger +
TodoWrite; the ledger remains source of truth because shared-task status can lag. (Otherwise no
external task daemon to sync — the ledger + TodoWrite together are the task view.)

### SET_GOAL(condition) / UPDATE_GOAL / GOAL_COMPLETE / GOAL_BLOCKED

Claude Code v2.1.139+ exposes `/goal` (Stop-hook evaluator after each turn). Requires trust dialog;
unavailable if `disableAllHooks`.

**SET_GOAL:** `/goal <condition>` immediately after ledger init. Condition must be verifiable from
Claude's transcript outputs (tests run, `git status`, file counts) AND reference `docs/` paths per
`runtime-goals.md`. Record under `## Runtime goal` in the ledger. Setting a goal starts a turn.

**UPDATE_GOAL:** No native tool — log progress in ledger `LAST_UPDATE` and TodoWrite. Evaluator
shows status on `/goal` with no args.

**GOAL_COMPLETE:** When ledger + readiness validate, either let the evaluator match the condition
or run `/goal clear` after file proof. Never clear before TERMINATE checks pass.

**GOAL_BLOCKED:** `/goal clear` + FINAL report with `status: blocked`; write readiness with
`fleet-outcome.status: blocked`.

**Ralph loop (task units only):** `/ralph-loop "<unit spec>" --completion-promise "TEXT"
--max-iterations N` for bounded single-unit work. Worker must output `<promise>TEXT</promise>`.
Do not replace full mission coordinator — Ralph lacks PR pipeline gates.

**Headless:** `claude -p "/goal <condition>"` — see `scripts/run-mission-headless.sh`.

**LOOP_POLL:** `/loop <interval> <prompt>` for CI/health polling only.

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

## STRICT MODE (optional Stop hook)
This adapter ships the reference implementation of the engine's `RUNTIME ENFORCEMENT GATE`: a Claude
Code Stop hook that refuses to end a worker session until verifiable evidence (EVID / WT_CLEAN /
e2e_verified / a passing verify-findings summary / test or e2e artifacts) exists on disk in a
freshness window. It is OPT-IN and fail-open (a broken gate degrades to loose mode, never traps a worker).
- Assets: `assets/hooks/stop-verify.sh` (wrapper) + `assets/hooks/hooks.json` (Stop-entry template).
- Install, configuration, discipline levels (loose / strict / paranoid), verify, and uninstall:
  see `autonomous-fleet-core/references/strict-mode.md`.
