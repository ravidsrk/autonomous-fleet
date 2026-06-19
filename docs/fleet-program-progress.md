# Fleet program progress

MODE: campaign
CAMPAIGN: composition-e2e
PHASE: DONE
ACTIVE_MISSION: none
CURRENT_NODE: none
BASE: fleet/composition-e2e-base

## Campaign spec

```yaml
campaign: composition-e2e
repo: single
base: fleet/composition-e2e-base
start: docs
nodes:
  docs: { mission: doc-sync }
  bugs: { mission: bug-batch }
  tests: { mission: test-coverage }
edges:
  docs:
    - { to: bugs, if: code_bug_findings > 0 }
    - { to: tests, if: always }
  bugs:
    - { to: tests, if: always }
  tests: []
```

## Last fleet-outcome

```yaml
mission: doc-sync
status: done
metrics:
  drift_open: 0
  code_bug_findings: 0
```

Branch decision: `code_bug_findings == 0` → **skip `bugs` node**, proceed to `tests` (verified via `./scripts/eval-campaign-edge.py`).

## Node status

| Node | Mission | Status | Readiness doc |
|------|---------|--------|---------------|
| docs | doc-sync | DONE | docs/doc-sync-readiness.md |
| bugs | bug-batch | SKIPPED | conditional edge false |
| tests | test-coverage | DONE | docs/test-coverage-readiness.md |

## Runtime goal

SCOPE: campaign
CONDITION: |
  Campaign composition-e2e DONE: docs/fleet-program-progress.md PHASE is DONE,
  every node in Node status is DONE or SKIPPED,
  docs/doc-sync-readiness.md and docs/test-coverage-readiness.md have valid fleet-outcome YAML,
  ./scripts/validate-fleet-outcome.sh passes on each readiness doc.
HOST: grok
SET_AT: 2026-06-20
LAST_UPDATE: Campaign complete — docs and tests nodes DONE; bugs SKIPPED (code_bug_findings == 0).

## Handoff notes

- Doc-sync closed D1–D5; added campaign tooling under `scripts/` and `tests/`.
- Test-coverage targets `scripts/lib/fleet_outcome.py` and campaign edge evaluator.