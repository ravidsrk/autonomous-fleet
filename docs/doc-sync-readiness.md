---
fleet-outcome:
  mission: doc-sync
  status: done
  repo: ravidsrk/autonomous-fleet
  base_branch: ravidsrk/dogfood-doc-sync
  prs_merged: 0
  metrics:
    drift_open: 0
    code_bug_findings: 0
  deferred_missions: []
  unverified_assumptions: 0
  sources_logged: 4
  cost_estimate: 0.3
  run:
    duration_min: 10
    note: dogfood of the engine disciplines shipped this week
---

# doc-sync readiness (dogfood of the new disciplines, 2026-06-21)

Closed the real README drift (new scripts + new engine disciplines undocumented) by running a
doc-sync mission with this week's engine disciplines active. One task unit, one PR.

## Drift closed
- README Layout `scripts/` block now lists `run-sandboxed.sh`, `coupling-graph.py`,
  `render-dashboard.py` (existed, were undocumented).
- "What every run guarantees" now notes the research discipline, per-task cost routing, the
  command-safety classifier, and optional container-use placement.

## Disciplines exercised (this is the dogfood)
- RESEARCH DISCIPLINE: every external fact the edits assert was monid-verified and logged to
  `docs/research-notes.md` (4 rows). `unverified_assumptions: 0`, `sources_logged: 4`.
- MODEL & COST ROUTING: builder = codex (mid tier), coordinator + reviewer = claude (strong tier),
  not flat-max. `cost_estimate: 0.3` (coarse; codex worker ~36k tokens + one monid search + the
  strong-tier coordinator turns).
- PLACE(independent) via container-use: the worker ran in an isolated container-use environment
  (`distinct-monarch`) on its own `container-use/<env>` branch; the change was reviewed via
  `container-use diff` and brought in via `container-use apply`. Real placement on a real mission.
- CROSS-VENDOR REVIEW + SHA-PIN: a codex builder's diff was reviewed by the claude coordinator
  (different vendor), diff-as-text only; `reviewed_sha: 5a4c3e0` recorded, re-review if HEAD moves.
- SIGNAL RECONCILIATION: before marking the unit done, the applied working-tree diff was confirmed
  equal to the reviewed env diff (external fact over ledger flag).
- COMMAND-SAFETY CLASSIFIER: the run's commands were classified by `scripts/run-sandboxed.sh`
  (`git push` -> ASK, `container-use apply` -> ALLOW, `rm -rf /` -> DENY).
- PLAN/DAG GATE + COUPLING: the frozen plan (one README unit, width 1, no cycles) passed the
  pre-spawn gate; coupling was trivial (single file).
- DASHBOARD: `scripts/render-dashboard.py` renders this ledger into the four attention zones.

## Recommended next missions
None. Single-unit doc-sync; clean.
