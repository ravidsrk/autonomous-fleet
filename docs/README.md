# `docs/` — index

The durable, user-facing surfaces live elsewhere: each skill's `SKILL.md` is the
source of truth, the top-level [`README.md`](../README.md) is the human front
door, and [`CONTRIBUTING.md`](../CONTRIBUTING.md) covers the Distillation
Discipline. This folder holds **design references, research, and point-in-time
run records** — useful as an audit trail, but read each with its date in mind.

> ⚠️ **Some files here are load-bearing.** The validators read them by glob:
> `*-progress.md` and `fleet-program-progress.md` (goal-condition checks) and
> `*-readiness.md` (fleet-outcome checks). Don't move or rename those without
> updating `scripts/validate_fleet_outcome.py` and `scripts/validate-goal-condition.sh`.

## Reference (durable)
- [`DECISIONS.md`](DECISIONS.md) — architectural decision log (the standing record).
- [`orchestration-landscape.md`](orchestration-landscape.md) — survey of orchestration runtimes.
- [`adopt-container-use.md`](adopt-container-use.md) — notes on the `container-use` placement option.

## Research (point-in-time explorations)
- [`research-skill-composition.md`](research-skill-composition.md), [`research-community-skills.md`](research-community-skills.md), [`research-runtime-loops-and-goals.md`](research-runtime-loops-and-goals.md), [`research-notes.md`](research-notes.md), [`gap-analysis-genesis-prompts.md`](gap-analysis-genesis-prompts.md)

## Run records — ledgers & readiness (load-bearing; validators read these)
- Progress ledgers: `arch-build-progress.md`, `doc-sync-progress.md`, `test-coverage-progress.md`, `fleet-program-progress.md`, `composition-e2e-goals.md`
- Readiness docs (carry `fleet-outcome` YAML): `arch-build-readiness.md`, `cleanup-readiness.md`, `close-gaps-readiness.md`, `doc-sync-readiness.md`, `mutation-gate-readiness.md`, `review-fix-readiness.md`, `test-coverage-readiness.md`, `test-hardening-readiness.md`, `secure-ship-e2e.md`

## Audits & reviews (point-in-time — numbers reflect their date)
- `adversarial-audit-2026-06-20.md`, `advreview-tests-review.md`, `arch-build-review.md`, `arch-build-review-rest.md`, `autonomous-fleet-review.md`, `composition-e2e-audit.md`, `doc-sync-audit.md`
- [`handoff-to-product.md`](handoff-to-product.md) — product handoff notes.

## Subdirectories
- [`exploratory/`](exploratory/) — patterns not yet validated by a real run (promoted into `engine.md`/`skills/` once a run cites them; see CONTRIBUTING).
- [`external-dogfood/`](external-dogfood/) — evidence from running the framework on external repos.
- [`marketplace-submission/`](marketplace-submission/) — launch + marketplace submission packets.
