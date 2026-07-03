---
name: autonomous-fleet-adapter-orca
description: >-
  First-class Orca adapter for autonomous-fleet-core — the reference runtime for supervised
  fleet missions. Maps engine primitives to Orca orchestration CLI commands (task-create,
  dispatch --inject, check --wait, worktree/terminal placement, worker_done/ask/reply, gh PR
  pipeline). Includes routing to orca-cli for full handoffs vs supervised fleet runs. Load with
  autonomous-fleet-core and one mission on Orca. Default roles: interactive @codex or @grok
  builds, fresh build-blind @claude reviews, @claude integrates. Trigger on Orca fleet runs,
  multi-agent PR pipelines on Orca, or when the host is Orca and autonomous-fleet is active.
license: MIT
compatibility: Requires Orca orchestration CLI, git, and gh CLI
metadata:
  author: "ravidsrk"
  version: "1.2.1"
  fleet-component: "adapter"
  reference-runtime: "orca"
---


# Adapter: Orca (reference runtime)

Runtime: [Orca](https://www.onorca.dev) — Settings → Experimental orchestration enabled;
`orca status --json` must show a running runtime. Branch prefix: `BRANCH_PREFIX` from core
self-orientation (default `fleet/`; recorded in DECISIONS.md).

**Orca is the reference runtime for autonomous-fleet.** It is the only host that gives
**structural** build-blind review (separate terminals per role) and matches the production
directives this framework was distilled from. Other adapters emulate Orca's loop via subagents
and ledger polling; they are supported but secondary for distribution.

This adapter resolves the core's PRIMITIVES to Orca commands. Where Orca's CLI differs across
versions, try X, fall back to Y — never hard-fail on one syntax.

Read [references/orca-platform.md](references/orca-platform.md) for the full routing table
(fleet vs `orca-cli` full handoff vs companion `orchestration` skill).

## ROUTING — fleet mission vs platform handoff

Before any primitive call, classify the user's intent:

| Intent | Path |
|--------|------|
| Fleet mission or campaign (`doc-sync`, `adversarial-review-and-fix`, `fleet-program`, …) | **This adapter** — supervised loop with `task-create` + `dispatch --inject` + `check --wait` |
| User says "hand off", "give to another agent/worktree" **without** asking to supervise/wait/DAG | **`orca-cli`** full handoff — **no** `task-create`, **no** `dispatch --inject`, **no** `check --wait` |
| Lightweight terminal prompt, worktree ops, embedded browser | **`orca-cli`** |
| User explicitly asks to supervise, monitor, wait for `worker_done`, coordinate a DAG | Supervised orchestration (this adapter for fleet; raw `orchestration` skill otherwise) |

Full-handoff examples (stop monitoring after prompt delivery):

```bash
orca worktree create --name <task> --no-parent --agent codex --prompt "<brief>" --json
# or: orca terminal send --terminal <handle> --text "<brief>" --enter --json
```

Custom Codex model/effort: create worktree, then `terminal create --command 'codex --model …'`,
wait `tui-idle`, `terminal send` — see `references/orca-platform.md`.

## PRECONDITIONS (the core calls for these; here's the Orca form)
`orca status --json` (running runtime) · orchestration experimental flag on · `gh auth status`
(else local merge-commits into BASE) · gitleaks availability · BASE exists (create off the default
branch at current HEAD if absent).

Machine-readable preflight requires-block:

```yaml requires
bins: [orca, git, gh]
env: []
auth:
  - check: "gh auth status"
    skip_if_intent: "no_scm"
intent_gated:
  scm: "willClaimExistingPR"
```

## PRIMITIVE → ORCA COMMAND

### PLACE(kind) → worker location
- `independent` → NEW worktree on its own branch off BASE (parallel PR). Pass `--repo REPO_ROOT`.
  Git base: omit `--base-branch` for repo default (`origin/main`), or set explicitly — never the
  current feature branch unless stacked work is intended. `--no-parent` only affects Orca lineage.
- `dependent` → ACTIVE worktree, **fresh** terminal session (same checkout; uncommitted state OK).
- **Fresh worker ≠ new git worktree.** Review-fix cycles and same-branch validation use dependent
  placement only.

### SPAWN_WORKER(role, placement) → handle, in auto/max mode
- INDEPENDENT:
  `orca worktree create --name <slug>-<run_short> --agent <cli> --repo REPO_ROOT --json`
  → `orca terminal list --worktree id:<newId> --json` (read the handle)
  → `orca terminal wait --terminal <handle> --for tui-idle --timeout-ms 60000 --json`
- DEPENDENT:
  `orca terminal create --worktree active --title <slug> --command "<cli>" --json`
  → `orca terminal wait --terminal <handle> --for tui-idle --timeout-ms 60000 --json`
- **Interactive agent CLIs** (supervised Orca — primary path):

  | Role | `--command` / `--agent` | Notes |
  |------|-------------------------|-------|
  | Builder | `codex` or `grok` | Mission role pipeline wins; `@grok` when mission says so |
  | Fresh build-blind reviewer | `claude` | Separate terminal — never the builder session |
  | Integrator | `claude` | PR open/merge only |
  | Design missions | `grok` | When mission specifies |

  Apply each CLI's auto/yolo/skip-permissions + effort tier at spawn; log in DECISIONS.md.
  Do **not** use `codex exec` for supervised Orca fleet runs — that subcommand is for headless
  drivers on other adapters. For custom Codex `--model` / effort, use the `terminal create
  --command 'codex …'` pattern in `references/orca-platform.md`.
- If an older CLI rejects `worktree create --agent`, create the worktree, then
  `orca terminal create --worktree <sel> --command "<cli>" --json`.
- **Ready** = `tui-idle`. NEVER DISPATCH before tui-idle (inject on a non-idle terminal is lost).
- Reuse an idle agent in the required worktree only when the mission allows; otherwise spawn fresh.

### DISPATCH(task, handle)
Build the inject payload: (1) mission `## Worker skills` for this role → **Worker skills:**
  "Activate and follow: `<names>`" per core engine.md; (2) task spec + completion contract
  (`worker_done` once, with `taskId` + `dispatchId`). Create task first:
  `orca orchestration task-create --spec "<spec>" [--deps <json>] [--parent <id>] --json`.
  Then: `orca orchestration dispatch --task <taskId> --to <handle> --inject --json`.
- **Bare shell target:** omit `--inject`; track with `task-create` if needed, deliver spec via
  `orca terminal send --terminal <handle> --text "<spec>" --enter --json`.

### WAIT(types, timeout)
`orca orchestration check --wait --types worker_done,escalation,decision_gate,merge_ready
--timeout-ms <n> --json`. Returns ONE message at a time — loop N times for N concurrent finishers.
Timeout / `{count:0}` = checkpoint, not failure. Heartbeats and terminal activity = alive, not
done — never kill a live worker. Rolling 15–60 min windows; on timeout inspect `task-list`,
`terminal read`, or `terminal wait --for tui-idle` as liveness before retrying.

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
--phase`). Target the CONCRETE coordinator handle from the live preamble — never a group
(`@all`, `@idle`, `@claude`, `@codex`, `@worktree:<id>`, … are broadcast-only).

**Review-only `worker_done`:** when the worker is reviewer-only, completion reports findings —
it does **not** authorize the coordinator to edit. Synthesize, gate if needed, dispatch fixes to
the builder role (or `orca-cli` handoff when the plan names a next owner).

### ASK / REPLY (worker blocking question / coordinator answer)
- Worker: `orca orchestration ask --to <coordinator> --question "<q>" --options "<a,b>"
  --timeout-ms 600000 --json` (consume inline, e.g. `| jq -r .answer`).
- Coordinator: `orca orchestration reply --id <msgId> --body <answer> --json`. Use
  `gate-create`/`gate-resolve` ONLY for your own DAG decisions, never to answer a worker's ask.

### OPEN_PR / MERGE_PR(conflict-aware) / CLEANUP
- OPEN_PR: `gh pr create --base BASE --head <BRANCH_PREFIX><slug>-<run_short> --title "<title>" --body "<body>"`.
- MERGE_PR: check conflicts first (`gh pr view <n> --json mergeable,mergeStateStatus` or a trial
  rebase). If conflicts: `git fetch origin BASE && git rebase origin/BASE`, resolve, re-test green,
  re-review if logic changed, force-push. Then `gh pr merge <n> --merge --delete-branch` (merge
  commit, commits preserved, NEVER `--squash`).
- CLEANUP (WT_CLEAN gate): verify MERGED + branch-deleted FIRST. Apply core engine guard clauses —
  NEVER remove the active worktree; NEVER remove an unmerged or dirty worktree. Version-tolerant:
  `orca worktree remove <id>` or `orca worktree archive <id>` (try X, fall back to Y). Set task-row
  `WT_CLEAN=true` in the ledger; pull BASE.

### SYNC_TASK_STATE(task, status)
`orca orchestration task-update --id <taskId> --status
<ready|dispatched|completed|failed|blocked> [--result '{"reason":...}'] --json` on every lifecycle
change, so `task-list --ready`/`--status` stay aligned with the file ledger (which remains source
of truth).

## TERMINAL TOOLKIT (coordinator)

```bash
orca terminal list [--worktree <selector>] --json
orca terminal create [--worktree <selector>] [--title <text>] [--command <cmd>] --json
orca terminal split --terminal <handle> [--direction horizontal|vertical] [--command <cmd>] --json
orca terminal wait --terminal <handle> --for tui-idle --timeout-ms <n> --json
orca terminal read --terminal <handle> --json
orca terminal send --terminal <handle> --text <text> --enter --json
```

## GATES AND `orchestration run`

```bash
orca orchestration gate-create --task <id> --question <text> [--options <json>] --json
orca orchestration gate-resolve --id <gate_id> --resolution <text> --json
orca orchestration run --spec <text> [--max-concurrent <n>] [--worktree <sel>] --json
orca orchestration run-stop --json
```

Worker blocking questions → `ask` + coordinator `reply` (creates `decision_gate` message).
`gate-create` is for **coordinator DAG decisions only**, not worker asks.

## DIAGNOSTICS
- Worker seems done but sent no `worker_done`: `dispatch-show --task <id> --preamble --json`;
  `terminal read` / `terminal wait --for tui-idle` as liveness. Re-send via `terminal send` if
  preamble was lost — never kill a live worker.
- Inherited stale preamble from terminal history or a prior full handoff → treat as absent unless
  the current fleet prompt re-attaches a live coordinator loop.
- NEVER `orca orchestration reset` during a fleet run (recovery-only when abandoning state).
- Orca circuit-breaks a dispatch after 3 consecutive failures → reassign per engine, not stop.

## RUNTIME GOALS (Orca — ledger-only)

Orca has no `/goal` API. Primitives 9–12 map to the file ledger only:

- **SET_GOAL:** Write `## Runtime goal` + `CONDITION:` in the program/mission ledger (documentation
  for humans and handoff). The coordinator `check --wait` loop IS the enforcement harness.
- **UPDATE_GOAL:** Append progress to ledger `LAST_UPDATE`; optional `send` heartbeat to coordinator.
- **GOAL_COMPLETE:** `PHASE: DONE` in ledger + FINAL report after TERMINATE checks.
- **GOAL_BLOCKED:** `escalation` message + `fleet-outcome.status: blocked`.

## Headless driver compatibility

`scripts/run-mission-headless.sh` and `scripts/run-campaign.sh` accept `grok`, `claude`, and
`codex` CLIs only — not the Orca app. **Production fleet runs on Orca use this adapter
interactively** in the Orca IDE: multi-terminal, cross-vendor roles, structural build-blindness.
Headless scripts are a CI/contributor path for other adapters; Orca distribution does not depend
on them.

## ORCA NOTES
- **Primary coordinator mode:** manual loop (`task-create` → spawn → `dispatch --inject` →
  `check --wait`) to keep file-ledger boolean-gate control — matches production directives.
  `orchestration run` is fallback only when the coordinator repeatedly stalls on context limits.
- Group addresses (`@all`, `@idle`, `@claude`, `@codex`, …) are for broadcasts only — never for
  dispatch lifecycle messages.
- Dependency chains ≤3–4 deep; one in-flight task per hot file; retire each worktree on merge.


## RESUMABILITY + REVIEWER ISOLATION (Wave 3 contract)

- run_short: every isolated branch and worktree carries the active run's 6-hex suffix
  (`<BRANCH_PREFIX><slug>-<run_short>`, `../<repo>-<slug>-<run_short>`, run_short = the 6-hex tail of
  the run_id) so parallel runs/checkouts never collide on a bare slug.
  `<SUBSTRATE>/validate_namespacing.py` enforces this.
- CONTINUE_WORKER(role, placement, session_handle): no documented session restore -> ALIAS to SPAWN_WORKER (idempotent relaunch). Re-attach only for `live`-classified
  rows (per `recovery_scan.py`); never re-attach a session whose PR merged or branch is gone. When a
  row's `RESUME_COUNT` hits `MAX_RESUME_ATTEMPTS` (3), escalate instead of continuing.
- Reviewer isolation: when role==reviewer, launch the worker via
  `scripts/run-sandboxed.sh --role reviewer -- <reviewer-cli>` so the candidate tree is read-only and
  only `.fleet/runs/<run_id>/` is writable.
