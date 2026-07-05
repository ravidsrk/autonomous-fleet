# Agent Orchestrator mechanism ports

## Attribution

| | |
|---|---|
| **Upstream** | [AgentWrapper/agent-orchestrator](https://github.com/AgentWrapper/agent-orchestrator) (formerly ComposioHQ/agent-orchestrator) |
| **Copyright** | Copyright 2026 Untrivial |
| **License** | [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0) |
| **AF relationship** | Clean-room ports as validators + engine doctrine — not a fork of the AO daemon/UI |

Repo-level credits: [`ATTRIBUTIONS.md`](../../../ATTRIBUTIONS.md) · [`NOTICE`](../../../NOTICE)

AF adopts **mechanisms**, not the product (no daemon, no Electron UI).

## Port map

| AO component | AF expression | Enforced by |
|---|---|---|
| `lifecycle/reactions.go` `sendOnce` | `nudge-state.json` + lib API | `verify_nudge_dedup.py` |
| `service/session/status.go` stacked PR | `pr-snapshot.json` + lib API | `verify_stacked_pr.py` |
| `service/session/status.go` `no_signal` | `activity_hooks` requires + trace | `verify_hook_signal.py` |
| Review `TargetSHA` supersede | `sha-pin.json` `superseded` field | `verify_sha_pin.py` |
| Signal reconciliation (already in engine) | `signals.md` § SIGNAL RECONCILIATION | coordinator discipline |
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

<!-- demoted from engine.md (issue #84) -->
═══════════════════════════════════════════════════════════
AO MECHANISMS — adopted from Agent Orchestrator (AgentWrapper/agent-orchestrator;
Apache 2.0, Copyright Untrivial — see references/ao-adoptions.md and ATTRIBUTIONS.md).
═══════════════════════════════════════════════════════════
See `references/ao-adoptions.md` for the full port map. These four close the remaining
mechanism gaps without adopting AO's daemon/UI:

PR-FEEDBACK NUDGE DEDUP (AO sendOnce): when routing CI failures, review comments, or
merge-conflict prompts to a worker, persist `.fleet/runs/<run_id>/nudge-state.json`
{pr_url, entries:[{key, kind, signature, attempts}]}. Before sending, check should_send_nudge;
after sending, record_nudge. Identical evidence (same signature) must NOT re-nudge; review kinds
cap at 3 attempts. Validated by `python3 <SUBSTRATE>/verify_nudge_dedup.py`.

STACKED-PR STATUS (AO status.go): a session may own multiple open PRs. Aggregate with worst-wins
severity. A child PR whose target_branch equals a sibling's source_branch while that parent is
still open is BLOCKED: suppress non-actionable child signals (mergeable/approved/review-pending)
but still surface ci_failed/changes_requested/draft. Merge-conflict nudges fire only for the stack
bottom. Snapshot to `pr-snapshot.json`; validated by `python3 <SUBSTRATE>/verify_stacked_pr.py`.

HOOK-SIGNAL HEALTH (AO no_signal): adapters with `activity_hooks: true` in the requires block
install a hook pipeline. After spawn/restore, 90s without any hook callback means no_signal, not
confident idle. INSPECT must record details.signal_state in trace events; `python3 <SUBSTRATE>/verify_hook_signal.py`
FAILs idle claims past grace with no callback.

REVIEW SUPERSEDE (AO review run supersede): when HEAD moves after a PASS, write a NEW sha-pin.json
(or sha-pins/<id>.json) for the new SHA and mark the prior approve record superseded: true. At most
one active approve per branch; `<SUBSTRATE>/verify_sha_pin.py` enforces both HEAD match and supersede invariants.
