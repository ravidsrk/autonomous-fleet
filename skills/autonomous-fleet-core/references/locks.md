# Locks

<!-- demoted from engine.md (issue #84) -->
═══════════════════════════════════════════════════════════
WRITE-LOCK DISCIPLINE — construction vs request locks.
═══════════════════════════════════════════════════════════
A worker that mutates shared state (the run-archive, a worktree branch, an external API) SHOULD
acquire the correct lock before the mutation and release it after WHEN multiple coordinators or
workers may write concurrently. (Status: the lock library is available and tested but has no
production call-site today — single-coordinator runs serialize through the file ledger. Wire it for
parallel-coordinator or shared-archive multi-writer setups.) LEDGER KEYING (issue #96): export
`FLEET_RUN_SHORT=<run_id's 6-hex tail>` right after allocating the run_id at SELF-ORIENTATION —
the mission registry then keys every ledger/readiness filename by run
(`<mission>-<run_short>-progress.md`, still matching every validator's `*-progress.md` glob), so
two concurrent same-mission runs no longer share a write target. RESIDUAL: a coordinator that
skips the export falls back to mission-keyed names and the old race; the steal() TOCTOU in the
lock library is fixed (CAS-shaped: tombstone rename + fresh link-acquire, never an in-place
overwrite). Two locks, two lifetimes:
- CONSTRUCTION LOCK: acquired before a worker starts BUILDING artifacts in its task slot
  (worktree, branch, attestation file). Released only on COMMIT or ABORT. Long-held. Prevents
  two workers racing to write the same artifact path under `.fleet/runs/<run_id>/`.
- REQUEST LOCK: acquired before a worker calls an external write API (`gh pr merge`,
  `terraform apply`, `fly deploy`, `git push`). Released immediately after the call returns.
  Short-held. Prevents a runaway worker from issuing duplicate side-effectful API calls.
A worker holding a construction lock MAY hold a request lock briefly; the reverse (long-held
request lock) is forbidden — request locks are taken just-in-time, never preemptively.
A lock whose holder process is dead (PID gone, ledger heartbeat stale) MAY be stolen by another
worker — but ONLY after the SIGNAL RECONCILIATION § dead-worker detection discipline has
confirmed the holder is gone. Stealing without a confirmed-dead signal is a protocol violation;
the lock library exposes the steal mechanism but the coordinator's circuit-breaker decides when
it's safe to invoke. Lock files live under `.fleet/runs/<run_id>/locks/` with contents
`{owner, acquired_at, pid}` for diagnostics. Implementation: `<SUBSTRATE>/lib/locks.py`.
