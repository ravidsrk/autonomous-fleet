# test-coverage progress (dogfood of the new disciplines, 2026-06-21)

PHASE: FIXING
MISSION: test-coverage   REPO: autonomous-fleet   BASE: ravidsrk/dogfood-test-coverage (off main@b84de27)
COORDINATOR: this Claude Code session

## SELF-ORIENTATION + COVERAGE MAP
Coverage run (coverage.py over scripts/) found the real gaps:
- `scripts/eval-campaign-edge.py` 0% (CLI, completely untested)
- `scripts/lib/mission_registry.py` 0% (readiness_path/progress_path, untested)
- `scripts/validate_fleet_outcome.py` 22% (validate CLI, mostly untested)
(fleet_outcome.py 92%, render-dashboard 88%, coupling-graph 79% are already covered.)

## COUPLING-AWARE PLACEMENT (real artifact this time)
`scripts/coupling-graph.py .` reports HUB = `scripts/lib/fleet_outcome.py` (in_degree 4,
serialize-always) and one coupled cluster {eval-campaign-edge, validate_fleet_outcome,
render-dashboard, fleet_outcome}. We are WRITING TESTS, not editing the hub, so the three test
FILES are independent and parallel-eligible; `mission_registry.py` imports nothing (fully standalone).

## PLAN / DAG VALIDATION GATE (SPOQ, pre-spawn)
Frozen units (each a NEW test file, no inter-dependencies):
- U1 tests/test_eval_campaign_cli.py  -> covers scripts/eval-campaign-edge.py
- U2 tests/test_mission_registry.py   -> covers scripts/lib/mission_registry.py
- U3 tests/test_validate_fleet_outcome_cli.py -> covers scripts/validate_fleet_outcome.py
GATE: no cycles, dependencies resolvable (none), parallelism WIDTH = 3. PASS. Hub fleet_outcome.py
is not edited, so no serialization needed.

## TASK ROW
TASK test-coverage-clis | FILES=[test_eval_campaign_cli,test_mission_registry,test_validate_fleet_outcome_cli]
| PLACE=container-use(independent) | WORKER=codex(cross-vendor to claude reviewer) | width-3 parallel-eligible
| CODED=f REVIEWED=f MERGED=f | reviewed_sha=- | NOTE=tests written in a container-use env; reviewer RUNS
them + checks they assert behavior (not coverage-padding).

## DISCIPLINES (evidence appended as the run proceeds)
- COVERAGE MAP -> real gaps (not invented). PLAN/DAG width 3. COUPLING -> hub identified.
- RESEARCH: test behaviors derived from in-repo code; few external facts (docs/research-notes.md).
- CONTAINER-USE placement; CROSS-VENDOR review (claude runs codex's tests); SHA-pin; SIGNAL
  RECONCILIATION (coverage re-measured externally, not trusted from the worker); COST routing;
  SAFETY classifier; DASHBOARD.
