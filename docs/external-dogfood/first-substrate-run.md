# First substrate run — real archive on autonomous-fleet (Lane 1)

**Status:** DONE (operator run completed 2026-06-27)  
**Closes gap:** A-real (way-ahead Commit A operator half)  
**Mission:** `adversarial-review-and-fix` on this repo (`main`)

## Why this run

The substrate validators and `example-fixture` prove the **mechanics**. This run produces the first
**field-hours** archive from a live coding-agent session with all four layers engaged on post-v0.1.0
code (headless trace, `fleet_run` orchestration, validate-headless).

## Disclosure — what this run is and is not

This is a **self-dogfood (Lane 1)**: autonomous-fleet running `adversarial-review-and-fix` against
**its own repo** (`ravidsrk/autonomous-fleet`, `main`). It validates the substrate end-to-end. It is
**not** proof of independent cross-pass review or of build-blindness, and it should not be cited as
either. Concretely, in this run:

- **Reviewer and skeptic artifacts are byte-identical.** `p0-review-findings.json` and
  `p0-skeptic-findings.json` share one sha256
  (`5de7255673c5b84e48e1f2900e213edeaec8cc16f4c556ec60107cec926c3306`), so the run does **not**
  demonstrate an independent skeptic pass distinct from the reviewer.
- **The metadata is internally inconsistent** (illustrative, not authoritative): `trace.jsonl`
  spans ~87s of events while `fleet-outcome.yaml` reports `duration_min: 45`; the trace records a
  `MERGE` with `status: succeeded` while `prs_merged: 0` (no PR landed); and most `manifest.json`
  mtimes are dated a day after `created_utc`.
- **Build-blindness is structural only in the cross-vendor / separate-process (Orca) case.** The
  shipped headless path runs one agent process per mission; on a single session it is fresh-context
  isolation (instructed), not a mechanical guarantee. No external run-archive with `prs_merged > 0`
  exists yet.

Treat this archive as gate-validation evidence (validators, trace emission, and `fleet_run`
orchestration over a live session) — not as independent-review or autonomous-landing proof. See the
fuller disclosure in `.fleet/runs/<run_id>/README.md`.

## Reproduction (operator)

### Prerequisites

- Grok CLI authenticated (`grok -p "ping"` succeeds)
- Skills installed in this repo (`./scripts/install-skills.sh` or equivalent)
- Clean `main` pulled (`git checkout main && git pull`)

### Kickoff

```bash
cd /path/to/autonomous-fleet
git checkout -b dogfood/first-substrate-run   # optional isolation branch

./scripts/run-mission-headless.sh grok adversarial-review-and-fix \
  --handoff docs/handoff-first-substrate-run.md \
  --max-turns 80
```

Ledgers for this run (not the 2026-06-21 arch-build dogfood):

- Progress: `docs/first-substrate-progress.md`
- Readiness: `docs/first-substrate-readiness.md`
- Frozen review: `docs/first-substrate-review.md` (created by Phase 0)

### Post-run validation

```bash
RUN_ID=<from readiness doc or .fleet/runs/>
./scripts/validate-first-substrate-archive.sh "$RUN_ID"
./scripts/validate-all.sh
```

Commit the archive (ephemeral dry-runs are gitignored; real archives are force-added):

```bash
git add docs/first-substrate-*.md docs/external-dogfood/first-substrate-run.md
git add -f .fleet/runs/"$RUN_ID"/
git commit -m "dogfood: first real substrate archive ($RUN_ID)"
```

## Post-run evidence

```
== validate-first-substrate-archive: .fleet/runs/20260626T200255Z-adversarial-review-and-fix-8358f1 ==
  Layer 4: validate_run_archive
  Layer 1: verify_findings
verify-findings: 2/2 findings verified
  unverified: 0
  auto_applicable: 2
  human_gated:     0
  Layer 3: verify_blind_fix
verify-blind-fix: 2/2 findings have valid blind-fix chains
  Trace: emit_trace validate
emit-trace: validated 17 events from trace.jsonl (0 invalid, 0 unparseable)
  Manifest cross-check (fleet_run)
  analyze_seat rollup
validate-first-substrate-archive: all checks passed for 20260626T200255Z-adversarial-review-and-fix-8358f1

./scripts/validate-all.sh → All checks passed (1031 tests, 100% scripts coverage).
```

## Archive inventory

| Artifact | Layer | Path |
|----------|-------|------|
| Findings | 1 | `.fleet/runs/<run_id>/p0-review-findings.json` |
| Verify summary | 1 | `.fleet/runs/<run_id>/p0-verify-summary.json` |
| Stop-verify log | 2 | `.fleet/runs/<run_id>/stop-verify-decisions.log` |
| Blind-fix files | 3 | `.fleet/runs/<run_id>/reviewer-blind-fix-*.md` |
| Manifest + trace | 4 | `.fleet/runs/<run_id>/manifest.json`, `trace.jsonl` |
| Outcome | — | `docs/first-substrate-readiness.md` |

## Comparison to example-fixture

| | example-fixture | first real run |
|--|-----------------|----------------|
| Origin | `scripts/_build_example_fixture.py` | Live Grok headless session |
| Run ID | `20260623T000000Z-adversarial-review-and-fix-000001` | `20260626T200255Z-adversarial-review-and-fix-8358f1` |
| Manifest files | 9 | 12 |
| Trace events | 11 (all primitives) | 17 (coordinator transitions + T-FINAL) |
| CI gate | `validate-all.sh` | Same validators + this doc |