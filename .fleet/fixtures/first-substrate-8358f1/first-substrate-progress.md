# first-substrate-progress (adversarial-review-and-fix on main, 2026-06-26)

PHASE: DONE
MISSION: adversarial-review-and-fix   REPO: autonomous-fleet   BASE: main
REVIEW_DOC: docs/first-substrate-review.md
COORDINATOR: grok headless via run-mission-headless.sh
RUN_ARCHIVE: .fleet/runs/20260626T200255Z-adversarial-review-and-fix-8358f1/

## SCOPE (frozen at kickoff)

Post-v0.1.0 substrate proof on **this repo** (`main`). Review and fix only:

- `scripts/lib/fleet_run.py`, `headless_trace.py`, `emit_trace.py`, headless entry points
- `scripts/run-mission-headless.sh`, `scripts/run-campaign.sh` (dry-run + `--repo` paths)
- `scripts/validate-headless.sh`, `scripts/validate_run_archive.py`, `scripts/verify_findings.py`, `scripts/verify_blind_fix.py`
- `.fleet/runs/example-fixture/` as the shape reference (do not mutate the fixture; produce a **new** `<run_id>`)

Out of scope: new missions, doctrine rewrites, Starlight site, external repos.

## PLAN / DAG VALIDATION GATE

Pending — coordinator fills frozen units after Phase 0 review.

## CLOSE-INDEX

| ID | Lane | State |
|----|------|-------|
| F-001 | A | CLOSED via dogfood/first-substrate-run |
| F-002 | A | CLOSED via dogfood/first-substrate-run |

## TASK ROWS

TASK fix-F-001 | FILES=scripts/lib/fleet_run.py,tests/test_headless_trace.py | CODED=t REVIEWED=t MERGED=t
TASK fix-F-002 | FILES=scripts/validate-first-substrate-archive.sh | CODED=t REVIEWED=t MERGED=t

## DISCIPLINES

- ARCHIVE_ENABLED: real `.fleet/runs/<run_id>/` with manifest + all four substrate layers
- TRACE: emit per-transition events where the coordinator performs transitions
- BLIND-FIX: Layer 3 chain for every closed finding
- STOP-VERIFY: Layer 2 log for every block/allow decision