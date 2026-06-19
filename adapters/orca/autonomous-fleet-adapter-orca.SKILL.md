---
name: autonomous-fleet-adapter-orca
description: >-
  The ORCA adapter for autonomous-fleet-core. Maps each engine PRIMITIVE (spawn worker, dispatch,
  wait, inspect, place, worker_done/ask/reply, open/merge PR, sync task state) to the real Orca
  orchestration CLI commands. Load this alongside autonomous-fleet-core when running a mission on
  Orca. Handles Orca's worktree/terminal model, --inject dispatch, check --wait supervision,
  version-tolerant worker_done, and task-update syncing. Default agent handles: @grok builds,
  @codex reviews (codex --full-auto), @claude integrates — overridable by the mission's role
  pipeline.
---

# Adapter: Orca

Runtime: [Orca](https://www.onorca.dev) orchestration (Settings → Experimental must be enabled;
`orca status --json` must show a running runtime). Branch prefix: use `BRANCH_PREFIX` from core
self-orientation (default `fleet/`; recorded in DECISIONS.md).

This adapter resolves the core's PRIMITIVES to Orca commands. Where Orca's CLI differs across
versions, the adapter says "try X, fall back to Y" — never hard-fail on one syntax.

## PRECONDITIONS (the core calls for these; here's the Orca form)
`orca status --json` (running runtime) · orchestration experimental flag on · `gh auth status`
(else local merge-commits into BASE) · gitleaks availability · BASE exists (create off the default
branch at current HEAD if absent).

## PRIMITIVE → ORCA COMMAND

### PLACE(kind) → worker location
- `independent` → a NEW worktree on its own branch off BASE (isolated checkout for a parallel PR).
- `dependent` → the ACTIVE worktree, a FRESH terminal (same checkout/branch).

### SPAWN_WORKER(role, placement) → handle, in auto/max mode
- INDEPENDENT:
  `orca worktree create --name <slug> --agent <handle> --repo REPO_ROOT --json`
  → `orca terminal list --worktree id:<newId> --json` (read the handle)
  → `orca terminal wait --terminal <handle> --for tui-idle --timeout-ms 60000 --json`
- DEPENDENT:
  `orca terminal create --worktree active --title <slug> --command "<cli>" --json`
  → `orca terminal wait --terminal <handle> --for tui-idle --timeout-ms 60000 --json`
- Agent CLI per role: builder `grok`, reviewer `codex --full-auto`, integrator `claude` (apply
  each CLI's auto/skip-permissions + max-effort flag; log in DECISIONS.md). If an older CLI rejects
  `--agent`, create the worktree then `orca terminal create --command "<cli>"`.
- "Ready" = `tui-idle`. NEVER DISPATCH before tui-idle (an inject on a non-idle terminal is lost).

### DISPATCH(task, handle)
`orca orchestration dispatch --task <taskId> --to <handle> --inject --json`
(`--inject` injects the task spec + preamble so the worker can report worker_done). Create the
task first: `orca orchestration task-create --spec "<spec>" [--deps <json>] --json`.

### WAIT(types, timeout)
`orca orchestration check --wait --types worker_done,escalation,decision_gate --timeout-ms <n>
--json`. Returns ONE message at a time — loop N times for N concurrent finishers. Timeout /
{count:0} = checkpoint, not failure.

### INSPECT() — non-destructive
`orca orchestration task-list --json` · `task-list --ready --json` · `orca orchestration inbox
--limit <n> --json` · `orca orchestration dispatch-show --task <id> --json`. (These do NOT mark
messages read. `check --all` also exists on newer CLIs — use if available, don't depend on it.
Reserve `check --unread`/default, which MARKS read, for when you intend to consume.)

### WORKER_DONE(...) — exactly once, even on failure — SYNTAX-TOLERANT
Must carry taskId + dispatchId + a short summary + files modified. Try one form; if rejected, the
other:
- payload: `orca orchestration send --to <coordinator> --type worker_done --subject "<short>"
  --body "<what·found·remains>" --payload
  '{"taskId":"<id>","dispatchId":"<id>","filesModified":["<path>"],"reportPath":"<opt>"}' --json`
- flags: same `send … --type worker_done --subject --body` with `--task-id <id> --dispatch-id <id>
  --files-modified "<path>[,…]" --report-path "<opt>"`.
Heartbeat likewise (payload `{"taskId","dispatchId","phase"}` OR `--task-id --dispatch-id
--phase`). Target the CONCRETE coordinator handle from the live preamble — never a group.

### ASK / REPLY (worker blocking question / coordinator answer)
- Worker: `orca orchestration ask --to <coordinator> --question "<q>" --options "<a,b>"
  --timeout-ms 600000 --json` (consume inline, e.g. `| jq -r .answer`).
- Coordinator: `orca orchestration reply --id <msgId> --body <answer> --json`. Use
  `gate-create`/`gate-resolve` ONLY for your own DAG decisions, never to answer a worker's ask.

### OPEN_PR / MERGE_PR(conflict-aware) / CLEANUP
- OPEN_PR: `gh pr create --base BASE --head <BRANCH_PREFIX><slug> --title "<title>" --body "<body>"`.
- MERGE_PR: check conflicts first (`gh pr view <n> --json mergeable,mergeStateStatus` or a trial
  rebase). If conflicts: `git fetch origin BASE && git rebase origin/BASE`, resolve, re-test green,
  re-review if logic changed, force-push. Then `gh pr merge <n> --merge --delete-branch` (merge
  commit, commits preserved, NEVER `--squash`).
- CLEANUP: archive/remove the merged branch's worktree (`orca worktree` remove/archive). Pull BASE.

### SYNC_TASK_STATE(task, status)
`orca orchestration task-update --id <taskId> --status
<ready|dispatched|completed|failed|blocked> [--result '{"reason":...}'] --json` on every lifecycle
change, so `task-list --ready`/`--status` stay aligned with the file ledger (which remains source
of truth).

## DIAGNOSTICS
- Worker seems done but sent no worker_done: `orca orchestration dispatch-show --task <id>
  --preamble --json` (confirm the completion instruction was injected); `terminal read` / `terminal
  wait --for tui-idle` as liveness. If the preamble lacked it, re-send via `terminal send` — never
  kill a live worker.
- NEVER `orca orchestration reset` during a run. Orca circuit-breaks a dispatch after 3 consecutive
  failures and marks the task failed — treat as a reassign signal, not a stop.

## ORCA NOTES
- Coordinator mode: manual loop (NOT `orchestration run`) to keep file-ledger boolean-gate control.
  `orchestration run --max-concurrent N --worktree <sel>` is the fallback only if a long run
  repeatedly stalls on coordinator context limits.
- Group addresses (`@all`, `@idle`, `@claude`, `@codex`, …) are for broadcasts only — never for
  dispatch lifecycle messages.
- Dependency chains ≤3–4 deep; one in-flight task per hot file; retire each worktree on merge.
