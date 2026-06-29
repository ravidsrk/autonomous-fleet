# Orca platform integration (companion to this adapter)

autonomous-fleet on Orca is a **supervised fleet-mission** layer on top of Orca's native
orchestration. This reference maps every case in Orca's `orchestration` skill to either this
adapter (fleet path) or a companion skill (`orchestration`, `orca-cli`).

## Routing table

| User intent | Skill / path | Lifecycle (`taskId`/`dispatchId`)? |
|-------------|--------------|-------------------------------------|
| Run a fleet mission (`doc-sync`, `adversarial-review-and-fix`, `fleet-program`, …) | **This adapter** + core + mission | Yes — supervised coordinator loop |
| Supervise workers, wait for `worker_done`, coordinate a DAG | Orca `orchestration` skill (this adapter implements it for fleet) | Yes |
| "Hand off", "give to another agent", one-shot ownership transfer | **`orca-cli`** — `worktree create --prompt` or `terminal send` | **No** — do not `task-create` / `dispatch --inject` / `check --wait` |
| Shell, worktree mgmt, read/wait terminals, embedded browser | **`orca-cli`** | No |
| Desktop / external browser UI | **Computer Use** (outside Orca embedded browser) | No |

Fleet coordinators **always** classify before spawning: if the user did not ask to supervise,
monitor, wait for results, or coordinate a DAG, route to `orca-cli` — not this adapter.

## Full handoff (non-fleet)

When ownership transfers without supervision:

```bash
# New top-level worktree + agent + prompt (no orchestration lifecycle)
orca worktree create --name <task> --no-parent --agent codex --prompt "<brief>" --json

# Existing terminal
orca terminal send --terminal <handle> --text "<brief>" --enter --json
```

Custom Codex model/effort (Orca cannot pass model flags on `worktree create --agent`):

```bash
orca worktree create --name <task> --no-parent --json
orca terminal create --worktree id:<id> --title <task> \
  --command 'codex --model <model> -c model_reasoning_effort="<effort>"' --json
orca terminal wait --terminal <handle> --for tui-idle --timeout-ms 60000 --json
orca terminal send --terminal <handle> --text "<brief>" --enter --json
```

After prompt delivery on a full handoff: **stop monitoring** unless the user explicitly asked
for supervision.

## Worktree lineage vs Git base

- `--no-parent` controls **Orca lineage** (top-level worktree in the Orca tree), not the Git base.
- For independent fleet workers: pass `--repo REPO_ROOT`; omit `--base-branch` to use the repo
  default (`origin/main` / `orca repo show`), or pass it explicitly. Never base on the current
  feature branch unless the mission requests stacked work.
- Fleet isolated branches still use `BRANCH_PREFIX` + `<slug>-<run_short>` per engine namespacing.

## Message types fleet coordinators handle

Include in `check --wait --types`:

`worker_done`, `escalation`, `decision_gate`, **`merge_ready`**

- **`merge_ready`**: integrator may proceed to `MERGE_PR` when review flags are true in the ledger.
- **`decision_gate` from worker `ask`**: answer with `reply`, not `gate-create`.
- **`gate-create`/`gate-resolve`**: coordinator DAG decisions only.

## Review-only `worker_done`

When the worker role is reviewer-only, `worker_done` reports findings — it does **not** authorize
the coordinator to edit files. After review-only completion: synthesize findings, use a decision
gate if ownership is unclear, then dispatch or `orca-cli` hand off fixes to the named builder role.

## Bare-shell workers

If the target terminal is a bare shell (not a recognized agent CLI): omit `--inject` on dispatch,
then deliver the task with `orca terminal send --terminal <handle> --text "<spec>" --enter --json`.

## Interactive builder CLIs (supervised fleet)

On Orca, fleet builders run as **interactive agent terminals**, not headless `codex exec`:

| Role | Terminal command | Notes |
|------|------------------|-------|
| Builder | `codex` or `grok` | Mission role pipeline wins; apply auto/yolo per CLI at spawn |
| Fresh build-blind reviewer | `claude` | New terminal; never the builder session |
| Integrator | `claude` | Opens/merges PRs; does not author fixes |
| Design missions | `grok` | When mission specifies |

Log spawn flags + model/effort in `DECISIONS.md`. `codex exec` is for **headless** drivers on
other adapters — not the primary Orca supervised path.