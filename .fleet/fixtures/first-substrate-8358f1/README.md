# QUARANTINED WIRING FIXTURE — formerly run archive 20260626T200255Z-adversarial-review-and-fix-8358f1

> **Quarantined out of `.fleet/runs/` (issue #78).** This directory is a
> wiring-validation fixture, **not** a run archive: never cite it as evidence of
> build-blind review, independent skeptic review, or autonomous PR landing. It
> was moved to `.fleet/fixtures/` so the run-archive validators and the
> promotion-evidence scan no longer treat it as a first-class run — its reviewer
> and skeptic findings are byte-identical (see Disclosure below), which a
> validated run archive must never exhibit (issue #77 adds that invariant).

First real substrate archive (Lane 1 dogfood).

## Disclosure — read before citing this archive

This is a **self-dogfood (Lane 1)**: autonomous-fleet running the
`adversarial-review-and-fix` mission against **its own repo** (`ravidsrk/autonomous-fleet`,
`main`). It exercises the substrate end-to-end, but it is **not** evidence of independent
cross-pass review or of build-blindness. Specifically:

- **Reviewer and skeptic artifacts are byte-identical in this run.**
  `p0-review-findings.json` and `p0-skeptic-findings.json` have the same sha256
  (`5de7255673c5b84e48e1f2900e213edeaec8cc16f4c556ec60107cec926c3306`). A genuine adversarial
  second pass would produce a distinct skeptic artifact; here it does not, so this run does
  **not** demonstrate independent reviewer/skeptic disagreement or convergence.
- **The metadata is internally inconsistent** and should be treated as illustrative, not
  authoritative:
  - `trace.jsonl` spans ~87s of events (20:04:01Z → 20:05:28Z) while
    `fleet-outcome.yaml` reports `run.duration_min: 45`.
  - The trace records a `MERGE` primitive with `status: succeeded`, but
    `fleet-outcome.yaml` reports `prs_merged: 0` — no PR was actually landed.
  - Most file `mtime_utc` values in `manifest.json` are dated `2026-06-27`, a day after
    `created_utc: 2026-06-26T20:05:28Z`.
- **Do not cite this archive as proof of build-blindness.** Build-blindness as a *mechanical*
  guarantee applies only to the cross-vendor / separate-process (Orca) case. The shipped
  headless path runs one agent process per mission; on a single session it is fresh-context
  isolation (instructed), not a mechanical guarantee. No external run-archive with
  `prs_merged > 0` existed when this fixture was produced (superseded 2026-07-03 by
  `.fleet/runs/20260703T054520Z-doc-sync-3e8173/` — see
  `docs/external-dogfood/gemoji-autonomous-run.md`).

This archive's value is that it shows the validators, trace emission, and `fleet_run`
orchestration running over a live session — gate-validation, not an independent-review or
autonomous-landing proof.
