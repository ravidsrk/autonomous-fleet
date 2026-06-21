---
fleet-outcome:
  mission: test-coverage
  status: done
  repo: ravidsrk/autonomous-fleet
  base_branch: ravidsrk/testcov-newcode
  prs_merged: 0
  metrics:
    gaps_open: 0
    coverage_regressed: false
  deferred_missions: []
  unverified_assumptions: 0
  sources_logged: 0
  cost_estimate: 0.15
  run:
    duration_min: 8
    note: test-coverage dogfood on this session's new code (the close-gaps + earlier PRs)
---

# test-coverage readiness — this session's new code (2026-06-21)

Covered the under-tested gaps in the python code added/changed this session. The CLIs were already
exercised via subprocess, which coverage.py cannot see (separate process), so the gaps were the
`main()` bodies and the error paths.

## Coverage closed (re-measured externally)

| module                              | before | after |
| ----------------------------------- | ------ | ----- |
| `scripts/coupling-graph.py`         | 75%    | 93%   |
| `scripts/render-dashboard.py`       | 88%    | 96%   |
| `scripts/validate_fleet_outcome.py` | 74%    | 89%   |
| TOTAL (scripts/)                    | 85%    | 94%   |

6 new tests in `tests/test_new_code_coverage.py`; full suite 208 -> 214.

## What got covered (real assertions, not padding)

- coupling-graph.py CLI `main()`: the `--json` path (assert clusters/hubs/files in the JSON), the
  human summary path (assert files:/clusters/hubs lines), and the non-directory `p.error` (SystemExit).
- render-dashboard.py CLI `main()`: writes the HTML to `-o` and the file is non-empty.
- validate_fleet_outcome.py: the `(ValueError, yaml.YAMLError)` except path added in the close-gaps
  work (a malformed-YAML doc fails with "invalid", exit 1) and the not-found path (exit 1).

## Discipline

- IN-PROCESS main() invocation: subprocess tests don't move coverage, so the CLIs are called in
  process via importlib (the lesson from the earlier test-coverage dogfood).
- SIGNAL RECONCILIATION: coverage was re-measured externally to confirm the gaps actually moved
  (75->93, 88->96, 74->89), not just that the suite is green.
- run-sandboxed.sh is bash (coverage.py cannot measure it); it carries 23 behavioural classify cases
  across test_sandbox_guard.py + test_adversarial_fixes.py.

## Notes

- gaps_open: 0 — the meaningful gaps in the new code are closed; the residual missed lines (coupling
  13, render 6, validate 5) are minor error-edge branches, not behaviour gaps.
- coverage_regressed: false (total 85 -> 94).
