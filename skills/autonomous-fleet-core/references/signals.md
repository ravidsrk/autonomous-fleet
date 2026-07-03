# Signals

<!-- demoted from engine.md (issue #84) -->
═══════════════════════════════════════════════════════════
SIGNAL RECONCILIATION — three signals, never transition on one read (from Agent Orchestrator;
Apache 2.0, Copyright Untrivial — see ATTRIBUTIONS.md).
═══════════════════════════════════════════════════════════
Three signals report task health and they DISAGREE in normal operation: worker-liveness (INSPECT),
the ledger flag you wrote, and the external SCM/CI fact (`gh pr view` state, CI conclusion). A
worker process can be dead while the runtime is alive, the ledger can say PR_OPEN while CI already
went red, the SCM can show merged while your flag still reads REVIEWED. Do NOT advance, escalate, or
declare a task stuck on the FIRST read that disagrees.
- ANTI-FLAP (require N consistent polls or a timeout): hold a contested task in a DETECTING state;
  only transition after N consecutive consistent polls (default 3) OR a hard timeout (default 5 min)
  elapses, whichever first. Key the counter to an evidence HASH of the contested signals (strip
  volatile fields like timestamps/activity counters before hashing): unchanged WEAK evidence
  re-presenting must NOT reset the counter, and genuinely NEW evidence resets it to 1. This stops a
  flapping signal from oscillating a task between states or resetting the stuck clock forever.
- EXTERNAL FACT OVERRIDES THE LEDGER (re-verify before any terminal flag): before writing ANY
  terminal flag (MERGED / DONE), re-verify the external fact directly (`gh pr view <n>
  --json state,mergedAt`, CI conclusion) and let it OVERRIDE the ledger when they disagree. If the
  SCM says merged but your flag does not, the SCM wins: record MERGED. If your flag says merged but
  the SCM says open/closed-unmerged, the SCM wins: do NOT mark DONE, record the discrepancy in
  DECISIONS.md, and re-drive the task. The ledger is your loop memory; the SCM/CI is ground truth at
  a terminal edge.
- A signal disagreement is a DETECTING checkpoint, not a failure. Reassign only after the 3-failure
  circuit-breaker, a confirmed worker exit, or the DETECTING timeout — never on a single poll.
