---
name: test-coverage
description: >-
  [Tier 1 · high autonomous success ~0.84 merge · safe to run unattended] Raise real test
  coverage on a repo or a target area with behaviour-exercising tests — not coverage-padding
  stubs. Use when a module is undertested, before a refactor to lock current behaviour,
  after a feature shipped without tests, or for a periodic coverage pass. Adds/strengthens
  unit, integration, and where relevant UI tests that genuinely assert behaviour; does NOT
  change application logic. Runs fully autonomously via the autonomous-fleet-core engine.
  Trigger on: "add tests", "raise coverage", "this module has no tests", "write tests for
  X", "improve test coverage", "lock current behaviour with tests".
license: MIT
metadata:
  author: "ravidsrk"
  version: "1.0.0"
  tier: "1"
  fleet-component: "mission"
---


# Mission: test-coverage

## Required skills

Before executing, activate these skills and read their full instructions:

1. `autonomous-fleet-core` — read `references/engine.md` and `references/composition.md` when coordinating
2. One runtime adapter: `autonomous-fleet-adapter-orca`, `autonomous-fleet-adapter-claude-code``, `autonomous-fleet-adapter-grok`, or `autonomous-fleet-adapter-codex`

Follow the core and your adapter in full, then apply the mission parameters below.

Do not load a second mission skill in the same run. For chained missions, use `fleet-program`.

## Optional skills

| Skill | Activate when | If unavailable |
|-------|---------------|----------------|
| — | — | — |

## Worker skills

| Role | Skills | If unavailable |
|------|--------|----------------|
| @claude (map, write tests, integrator) | — | Match repo test framework from T-MAP |

## Deferred missions

Record in `docs/test-coverage-readiness.md` under **Recommended next missions** and in DECISIONS.md.

| Finding type | Route to |
|--------------|----------|
| Logic change needed to make code testable | `bug-batch` or scoped fix mission |
| Refactor required for testability | `cleanup` (light) or `targeted-migration` |
| Hollow coverage tooling only | Use repo's existing test/coverage commands |

**Empirical note:** test tasks merge at ~0.84 across 33k real agent PRs — high-trust, safe
unattended. The ONE failure mode to guard is hollow tests written to move a number; the reviewer
rejects those.

## GOAL
Increase MEANINGFUL test coverage on the target (whole repo, or an area the user named). Every
added test must exercise real behaviour and fail if that behaviour breaks. Cover the important
paths: core logic, edge/error/empty cases, and regression-prone areas. Do NOT chase a vanity
percentage with trivial assertions; do NOT change application logic to make testing easier
(record any such need as a finding). Coverage must rise on real tests and never regress.

## ROLE PIPELINE
- @claude identifies coverage gaps and WRITES the tests.
- @codex REVIEWS each PR (fresh, build-blind): tests assert real behaviour, would FAIL if the
  code broke (not tautological), cover meaningful paths, no coverage-padding, no logic changed.
- @claude is the INTEGRATOR: opens PR, merges (conflict-aware), cleans worktree.

## LEDGER
`docs/test-coverage-progress.md`. Per-task flags: `WRITTEN=<t/f> PR_OPEN=<t/f> REVIEWED=<t/f>
MERGED=<t/f>`. Plus a GAP INDEX: each undertested area found in T-MAP, `OPEN | COVERED via PR#n`,
with before/after coverage where the tooling reports it.

## TASK STRUCTURE
- **T-MAP [@claude]** — run the existing suite + coverage tooling; map the undertested areas by
  importance (core logic and regression-prone paths first, trivial getters last). Identify the
  test framework + conventions already in the repo (match them). Output
  `docs/test-coverage-map.md`. Freeze, then fill.
- **T-COVER… [per area, loop]** — each area is one PR. @claude writes behaviour-exercising tests
  for that area (verify they FAIL against intentionally-broken code, then pass) → @codex reviews
  (real assertions, meaningful paths, no padding) → @claude merges. Parallelize across
  non-overlapping test files; serialize same-file. Update the GAP INDEX + coverage deltas.
- **T-FINAL [@claude]** — full suite green; coverage rose on the mapped areas and did not
  regress elsewhere. Output `docs/test-coverage-readiness.md` with **`fleet-outcome` YAML**
  (`gaps_open`, `coverage_regressed`), gap/coverage summary, **Recommended next missions**, all
  PRs. Ship as the final PR.

## Runtime goal

After ledger init, **SET_GOAL** per `autonomous-fleet-core/references/runtime-goals.md`. Record
`## Runtime goal` in `docs/test-coverage-progress.md`. **GOAL_COMPLETE** only after ## DONE below.

```
Mission test-coverage DONE: docs/test-coverage-progress.md all task flags true,
docs/test-coverage-readiness.md with fleet-outcome.status done and mission metrics satisfied,
./scripts/validate-fleet-outcome.sh passes, all PRs merged into BASE.
```


## DONE
Every GAP-INDEX item `COVERED`, every task terminal, suite green, coverage not regressed,
`docs/test-coverage-readiness.md` exists. Then send the FINAL report.

## DECISION DEFAULTS (mission-specific)
- Tests must FAIL if the behaviour they cover breaks. A test that passes against broken code is
  rejected — write it to assert behaviour, not to exist.
- Never change application logic to make testing easier; record the need as a finding for
  another mission.
- Match the repo's existing test framework, structure, and naming. Don't introduce a new harness
  unless none exists.
- Prioritize core logic, edge/error/empty cases, and regression-prone code over trivial members.
- Prefer many small per-area PRs over one giant test PR.
- Any ambiguity → the test that best protects real behaviour from regressions.
