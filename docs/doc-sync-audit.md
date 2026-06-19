# doc-sync audit — autonomous-fleet (first trial)

> **Superseded** by `composition-e2e-audit.md` and `doc-sync-readiness.md` (fleet-outcome run on
> `fleet/composition-e2e-base`). Kept for history — all items below were **CLOSED** via PR #1 and
> later README updates on `main`.

Frozen discovery artifact for the initial doc-sync dogfood (pre-`fleet-outcome`).

## DRIFT INDEX (historical)

| ID | Area | Resolution |
|----|------|------------|
| D1 | `.agents/` copies not symlinks | CLOSED — documented in README |
| D2 | skill-creator not bundled | CLOSED — step 1 in README |
| D3 | `.agents/` gitignored | CLOSED — documented in README |
| D4 | validate-skills needs skill-creator | CLOSED — documented in README §Validate |

## Verified at time of first trial

- `skills/` publishable packages (then 16; now **18** with `autonomous-fleet` + `fleet-program`).
- `./scripts/validate-skills.sh` passes when skill-creator is installed.

## Deferred (not doc drift)

- Mission `@claude`/`@codex` role labels — pipeline convention, not README drift.