# composition-e2e — reasoning log

End-to-end dogfood of the composition stack: **worker-skills (spec)**, **fleet-outcome YAML**,
**conditional campaign DAG**, and **executable validators** (the gap between skill-only and
runnable tooling).

## Why this campaign

| Goal | How this run proves it |
|------|------------------------|
| Mission chain | `doc-sync` → conditional skip → `test-coverage` |
| Conditional edge | `docs-if-bugs` pattern: branch on `code_bug_findings` |
| fleet-outcome | Readiness docs parsed by `validate-fleet-outcome.sh` |
| Campaign evaluator | `eval-campaign-edge.py` picks next node from YAML |
| No parallel same-repo | Single `ACTIVE_MISSION`; bugs node SKIPPED not concurrent |

We did **not** run `bug-batch` because doc-sync reported `code_bug_findings: 0` — the first
matching edge after the false `> 0` check is `always` → `tests`.

## Architecture: three layers of “orchestration”

```
┌─────────────────────────────────────────────────────────┐
│  fleet-program (campaign coordinator)                   │
│  - reads campaign YAML                                  │
│  - reads fleet-outcome from readiness                   │
│  - eval-campaign-edge.py (optional mechanical check)    │
└───────────────────────┬─────────────────────────────────┘
                        │ one mission at a time
┌───────────────────────▼─────────────────────────────────┐
│  mission skill (doc-sync, test-coverage, …)               │
│  - Worker skills → DISPATCH preamble (agent-enforced)     │
│  - T-FINAL → fleet-outcome YAML                           │
└───────────────────────┬─────────────────────────────────┘
                        │ tasks / PRs
┌───────────────────────▼─────────────────────────────────┐
│  autonomous-fleet-core + adapter                          │
│  - hot-file parallelism inside mission only               │
└─────────────────────────────────────────────────────────┘
```

**Reasoning:** Skill text governs agent behaviour; scripts govern **parseable contracts**. Without
`validate-fleet-outcome.sh` and `eval-campaign-edge.py`, conditionals are honor-system. This run
adds mechanical checks so campaigns can be tested in CI later.

## Node-by-node

### 1. doc-sync (`docs`)

**Drift found:** README/scripts layout stale; install-skills said 16 skills; prior readiness lacked
`fleet-outcome`.

**Fix:** Document new scripts; retrofit readiness YAML; close D1–D5 in audit.

**Outcome metrics:** `code_bug_findings: 0` → campaign skips `bugs`.

### 2. bug-batch (`bugs`) — SKIPPED

Not executed. Edge `code_bug_findings > 0` evaluated **false** via:

```bash
./scripts/eval-campaign-edge.sh \
  --readiness docs/doc-sync-readiness.md \
  --expr "code_bug_findings > 0"
# exit 1 → false
```

### 3. test-coverage (`tests`)

**Gap:** No automated tests for campaign machinery.

**Fix:** `tests/test_fleet_campaign.py` — parser, validator, `pick_next_node`, conditional branch.

**Outcome:** `gaps_open: 0`, `coverage_regressed: false`.

## What is still agent-driven vs mechanical

| Concern | Agent (skills) | Mechanical (scripts) |
|---------|----------------|----------------------|
| Run missions | ✓ coordinator loop | — |
| Worker loads frontend-design | ✓ DISPATCH preamble | — |
| fleet-outcome shape | ✓ T-FINAL instructions | `validate-fleet-outcome.sh` |
| Campaign branch | ✓ fleet-program skill | `eval-campaign-edge.py` |
| PR pipeline | ✓ core + adapter | `gh` + git |

## Explicit non-goals (unchanged)

- Parallel missions on one repo
- Full autonomous campaign runner daemon (future: `run-campaign.sh` orchestrating git/gh)

## Campaign complete

`PHASE: DONE` when both readiness docs validate and pytest passes.