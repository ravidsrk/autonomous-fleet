# DURABLE-EXECUTION PATCHES (exploratory)

Moved out of `engine.md` on 2026-06-22. The pattern is plausibly load-bearing
but does NOT appear in any progress doc or readiness doc from a real
autonomous-fleet run. It surfaced in the orchestration-landscape research
scan (`docs/orchestration-landscape.md`) and was prematurely promoted to
engine-level.

Re-promote to `engine.md` only after a real run validates the pattern.

---

═══════════════════════════════════════════════════════════
DURABLE-EXECUTION PATCHES — exactly-once, bounded waits, compensation. On the LEDGER, not a runtime.
═══════════════════════════════════════════════════════════
A coordinator restart (compaction drop, host crash, fresh resume from CONTEXT HANDOFF) must not
double-ship or hang. These three patches buy the durable-execution properties WITHOUT a runtime —
they live on the ledger, the same external brain you already re-read every turn.
- IDEMPOTENCY KEY per task: stamp each task row with a stable key (e.g. `<slug>@<branch>`). Before a
  side-effecting primitive (OPEN_PR, MERGE_PR) check the ledger + external fact for that key first: a
  re-issued OPEN_PR when a PR# already exists for the key is a NO-OP (reuse the recorded PR#), a
  re-issued MERGE_PR when `gh pr view` already reads merged is a NO-OP (record MERGED, move on). So a
  restart that re-drives a half-finished task converges instead of opening a duplicate PR or
  double-merging. Pairs with SIGNAL RECONCILIATION's re-verify-before-terminal rule.
- MANDATORY DEADLINE + ESCALATION on every WAIT()/ASK(): no unbounded wait. Every WAIT() carries a
  timeout and every open ASK carries a deadline; on expiry, take the checkpoint action (re-issue
  WAIT per AUTONOMY ENFORCEMENT) up to a bounded number of cycles, then GOAL_BLOCKED with a clear
  note rather than waiting forever. A worker that never reports and never exits is a blocked task,
  not an immortal one.
- COMPENSATION NOTE for circuit-breaker trips in a dependent chain: when a task trips the 3-failure
  breaker and downstream tasks already consumed its partial side-effects (a pushed branch, an open
  PR, a half-applied migration), record a defined ROLLBACK in DECISIONS.md (close the orphan PR,
  delete the dead branch, revert the partial commit on BASE) and run it before reassigning, so the
  chain restarts from a clean state. A trip is a saga rollback point, not just a stop.
- This is deliberately the LIGHT option: idempotency-key + deadline + compensation on a flat-file
  ledger. If a mission ever needs heavier durability (replay, exactly-once across processes, typed
  sagas), run the DAG on Temporal / Inngest (or DBOS / Restate, or a LangGraph checkpointer +
  interrupt()) instead of growing this by hand — see orchestration-landscape.md.
