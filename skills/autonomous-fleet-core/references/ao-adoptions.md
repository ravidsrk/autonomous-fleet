# Agent Orchestrator mechanism ports

Source repo: [AgentWrapper/agent-orchestrator](https://github.com/AgentWrapper/agent-orchestrator)
(formerly ComposioHQ). AF adopts **mechanisms**, not the product (no daemon, no Electron UI).

## Port map

| AO component | AF expression | Enforced by |
|---|---|---|
| `lifecycle/reactions.go` `sendOnce` | `nudge-state.json` + lib API | `verify_nudge_dedup.py` |
| `service/session/status.go` stacked PR | `pr-snapshot.json` + lib API | `verify_stacked_pr.py` |
| `service/session/status.go` `no_signal` | `activity_hooks` requires + trace | `verify_hook_signal.py` |
| Review `TargetSHA` supersede | `sha-pin.json` `superseded` field | `verify_sha_pin.py` |
| Signal reconciliation (already in engine) | `engine.md` § SIGNAL RECONCILIATION | coordinator discipline |
| SHA-pin at PASS (already shipped) | `sha-pin.json` | `verify_sha_pin.py` |
| Recovery scanner (already shipped) | `recovery_scan.py` | advisory at resume |
| `CONTINUE_WORKER` (already shipped) | engine primitive 14 | adapter SKILL.md |

## Coordinator obligations

1. On SCM poll detecting actionable feedback, update `nudge-state.json` before DISPATCH.
2. On multi-PR tasks, write `pr-snapshot.json` when session status is derived from `gh pr view`.
3. On INSPECT for hook-capable workers, emit `details.hook_callback` or `details.signal_state`.
4. On fix-round push after PASS, supersede the old sha-pin before setting REVIEWED again.

## Kill switches

Contract/budget verifiers (escape-hatch class):

- `FLEET_DISABLE_NUDGE_DEDUP`
- `FLEET_DISABLE_STACKED_PR`
- `FLEET_DISABLE_HOOK_SIGNAL`

See `references/substrate-disable-knobs.md`.