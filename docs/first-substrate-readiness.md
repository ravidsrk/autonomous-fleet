---
fleet-outcome:
  mission: adversarial-review-and-fix
  status: in_progress
  repo: ravidsrk/autonomous-fleet
  base_branch: main
  prs_merged: 0
  metrics:
    p0_open: 0
    p1_open: 0
    findings_open: 0
    ops_queue_count: 0
  deferred_missions: []
  unverified_assumptions: 0
  sources_logged: 0
  cost_estimate: 0
  run:
    duration_min: 0
    note: first real substrate archive — pending operator run completion
  archive_enabled: false
  run_id: null
---

# first-substrate readiness — pending

This doc is filled when the run completes. Done means:

- `docs/first-substrate-progress.md` has `PHASE: DONE` and all task flags true
- `.fleet/runs/<run_id>/` exists and passes `./scripts/validate-first-substrate-archive.sh <run_id>`
- `fleet-outcome.status: done` and `archive_enabled: true` with `run_id` set
- `docs/external-dogfood/first-substrate-run.md` updated with reproduction steps and validator output