---
fleet-outcome:
  mission: adversarial-review-and-fix
  status: done
  repo: ravidsrk/autonomous-fleet
  base_branch: ravidsrk/dogfood-adversarial-rest
  prs_merged: 0
  metrics:
    p0_open: 0
    p1_open: 0
    findings_open: 0
    ops_queue_count: 0
  deferred_missions: []
  unverified_assumptions: 0
  sources_logged: 0
  cost_estimate: 2.6
  run:
    duration_min: 35
    note: adversarial-review-and-fix across the REST of the codebase (everything PR #26 did not cover)
---

# arch-build-readiness — adversarial review of the REST of the codebase (2026-06-21)

Ran the adversarial-review-and-fix dogfood across everything PR #26 did not touch: the CLIs +
fleet_outcome older code, 8 shell scripts, engine.md + 4 references, 5 adapters, 17 missions, 6
campaigns. 12 confirmed findings (frozen in docs/arch-build-review-rest.md), all closed.
`findings_open: 0`, `p0_open: 0`, `p1_open: 0`, `ops_queue_count: 0`.

## The 3 P1s (real coordination/host bugs)
- D1: the campaign runner silently reported a `status: blocked` node as a completed campaign. It now
  halts with a distinct "Campaign BLOCKED" message + exit 2 (the GOAL_BLOCKED contract).
- E-2: headless `codex exec` is single-shot and ignores `/goal`, so the headless prompt's `/goal` was
  inert with no continuation harness. Documented: headless codex needs an external LOOP_POLL.
- F1-missions: the runner's unconditional cycle abort made handoff-to-product's designed back-edges
  un-runnable. Replaced with a per-node revisit budget (3) under the existing step cap.

## The 9 P2s
eval_edge trailing-token silent misroute (F1); pick_next_node crash on missing-metric edge (F2) and
None-on-missing-`to` (F4); validate CLI aborting on malformed YAML (F3); run-campaign stale-venv crash
(B2); undefined circuit-breaker in engine.md (C4); `container-use merge into BASE` claim wrong in 3
adapters (E-1); orca `codex --full-auto` rejected (E1); grok hardcoded model id rejected (E2).

## Process note (honesty)
A transient API rate-limit wave truncated the first review pass (2 of 6 partitions + several verifiers
failed). The review was RESUMED to complete coverage; the resume's stochastic finders surfaced a
different, larger set, so the true confirmed set is the union of both passes (3 + 9 = 12). Every
finding was reproduced and verified by 2 refuters before fixing.

## Verification
- pytest 186 passed; validate-all green.
- run-campaign.sh dry-run green; the F4 / cycle / revisit-budget tests updated to the new behavior.
- Adapter descriptions within the 1024-char skill limit.

## OPS / human boundary
None. All fixes code-only, verified on fixtures + dry-run. No secret, deploy, or destructive op run.
