# first-substrate-progress (adversarial-review-and-fix on main, 2026-06-26)

PHASE: PLAN
MISSION: adversarial-review-and-fix   REPO: autonomous-fleet   BASE: main
REVIEW_DOC: (pending — operator run will freeze under docs/first-substrate-review.md)
COORDINATOR: grok headless via run-mission-headless.sh
RUN_ARCHIVE: (pending — .fleet/runs/<run_id>/)

## SCOPE (frozen at kickoff)

Post-v0.1.0 substrate proof on **this repo** (`main`). Review and fix only:

- `scripts/lib/fleet_run.py`, `headless_trace.py`, `emit_trace.py`, headless entry points
- `scripts/run-mission-headless.sh`, `scripts/run-campaign.sh` (dry-run + `--repo` paths)
- `scripts/validate-headless.sh`, `scripts/validate_run_archive.py`, `scripts/verify_findings.py`, `scripts/verify_blind_fix.py`
- `.fleet/runs/example-fixture/` as the shape reference (do not mutate the fixture; produce a **new** `<run_id>`)

Out of scope: new missions, doctrine rewrites, Starlight site, external repos.

## PLAN / DAG VALIDATION GATE

Pending — coordinator fills frozen units after Phase 0 review.

## TASK ROWS

(none yet)

## DISCIPLINES

- ARCHIVE_ENABLED: real `.fleet/runs/<run_id>/` with manifest + all four substrate layers
- TRACE: emit per-transition events where the coordinator performs transitions
- BLIND-FIX: Layer 3 chain for every closed finding
- STOP-VERIFY: Layer 2 log for every block/allow decision