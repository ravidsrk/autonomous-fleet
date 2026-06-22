---
fleet-outcome:
  mission: test-coverage
  status: done
  repo: ravidsrk/autonomous-fleet
  base_branch: ravidsrk/mutation-gate
  prs_merged: 0
  metrics:
    gaps_open: 0
    coverage_regressed: false
  deferred_missions: []
  unverified_assumptions: 0
  sources_logged: 0
  cost_estimate: 1.4
  run:
    duration_min: 40
    note: standing mutation gate + scripts/ coverage to 100% with a fail-under gate
---

# mutation-gate readiness — standing spot-check + 100% coverage (2026-06-22)

Two standing gates, plus the coverage to back them.

## 1. Standing mutation gate (the spot-check, now repeatable)

- `tests/mutations.yaml`: a manifest of 11 representative bugs in the critical mechanisms (e2e gate,
  non-finite guard, unknown-mission check, eval missing-metric, blast-radius rm-catastrophic,
  campaign blocked-halt + revisit budget, coupling relative-imports, and the three prose rails) each
  paired with the test(s) that MUST catch it.
- `scripts/mutation_check.py` + `scripts/mutation-check.sh`: apply each mutation, run its guard tests,
  assert they FAIL (caught), and restore (try/finally + signal handler + git-checkout net; refuses on
  a dirty tree). Wired into CI as its own step.
- Result: 11 mutations, 11 caught, 0 survived, 0 stale.
- The gate is self-tested (proven non-inert): `tests/test_mutation_check.py` forces a weak guard and a
  drifted entry and asserts the gate FAILS (reports SURVIVED / STALE), and asserts it restores files.

## 2. scripts/ coverage to 100%, held by a fail-under gate

- Every scripts/ module is now 100% covered (TOTAL 625/625). `validate-all.sh` runs pytest under
  coverage with `--fail-under=100`, so a future uncovered line fails the build.
- `.coveragerc` excludes only genuinely-unhittable lines (`if __name__ == .__main__.:`,
  `raise SystemExit`, `# pragma: no cover`); one justified parser pragma on an invalid-syntax branch.
- The new coverage tests are mutation-strong, not padding: mutating each newly-covered branch
  (parse_readiness errors, the validate CLI no-docs/SKIP paths, coupling import edges, the eval CLI
  error path) fails its test.

## Honest scope note

"100%" here means line coverage = 100% and the 11 manifest mutations are all caught. Mutation testing
is still a curated sample, not a proof of zero weak tests; the gate's value is that the sample now
runs every build and grows by one entry whenever a mechanism is added. The standing gate converts the
one-shot mutation review into a recurring check.

## Verification

- validate-all green (incl. the coverage 100% gate); mutation gate 11/11 caught; suite green.
- Human-owned follow-up (NOT done): none new; BASE->main is the normal review+merge.
