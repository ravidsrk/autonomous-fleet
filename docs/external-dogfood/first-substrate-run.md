# First substrate run — real archive on autonomous-fleet (Lane 1)

**Status:** DONE (operator run completed 2026-06-27)  
**Closes gap:** A-real (way-ahead Commit A operator half)  
**Mission:** `adversarial-review-and-fix` on this repo (`main`)

## Why this run

The substrate validators and `example-fixture` prove the **mechanics**. This run produces the first
**field-hours** archive from a live coding-agent session with all four layers engaged on post-v0.1.0
code (headless trace, `fleet_run` orchestration, validate-headless).

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
emit-trace: validated 14 events from trace.jsonl (0 invalid, 0 unparseable)
  Manifest cross-check (fleet_run)
  analyze_seat rollup
validate-first-substrate-archive: all checks passed for 20260626T200255Z-adversarial-review-and-fix-8358f1

./scripts/validate-all.sh → All checks passed.
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
| Trace events | 11 (all primitives) | 14 (coordinator transitions + T-FINAL) |
| CI gate | `validate-all.sh` | Same validators + this doc |